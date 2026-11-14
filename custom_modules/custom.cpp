#include "custom.h"

/*
    Módulo Personalizado: Esferoide Tumoral SW480 vs Tejido Sano tratado con Parasporina.
    Integración Multiescala: Cinética GROMACS 500ns MD + BioFVM + Mecánica Celular
*/

void create_cell_types( void )
{
    // Inicializa las definiciones desde el XML
    initialize_cell_definitions_from_pugixml();

    Cell_Definition* pSW480 = find_cell_definition("SW480");
    if( pSW480 != NULL )
    {
        pSW480->functions.update_phenotype = sw480_phenotype_rule;
        pSW480->functions.custom_cell_rule = parasporin_ode_rule;
        std::cout << "SW480 (Cancer) configurada con reglas de ODEs de Parasporina." << std::endl;
    }

    Cell_Definition* pHealthy = find_cell_definition("Healthy_Epithelial");
    if( pHealthy != NULL )
    {
        pHealthy->functions.update_phenotype = healthy_phenotype_rule;
        pHealthy->functions.custom_cell_rule = parasporin_ode_rule;
        std::cout << "Healthy Epithelial (Sana) configurada con reglas de ODEs de Parasporina." << std::endl;
    }

    display_cell_definitions( std::cout );
    return;
}

void setup_microenvironment( void )
{
    initialize_microenvironment();
    return;
}

void setup_tissue( void )
{
    Cell_Definition* pSW480 = find_cell_definition("SW480");
    Cell_Definition* pHealthy = find_cell_definition("Healthy_Epithelial");

    if( pSW480 == NULL || pHealthy == NULL )
    {
        std::cerr << "Error: No se encontraron las definiciones celulares en setup_tissue!" << std::endl;
        return;
    }

    double tumor_radius = 200.0;         // Radio del núcleo tumoral SW480 (200 um)
    double healthy_outer_radius = 360.0; // Radio exterior del tejido sano (200 a 360 um)
    double cell_spacing = 16.0;          // Distancia entre centros celulares (16 um)

    int sw480_count = 0;
    int healthy_count = 0;

    for( double x = -healthy_outer_radius; x <= healthy_outer_radius; x += cell_spacing )
    {
        for( double y = -healthy_outer_radius; y <= healthy_outer_radius; y += cell_spacing )
        {
            double r_sq = x*x + y*y;

            // 1. Núcleo Tumoral SW480 (r <= 200 um)
            if( r_sq <= tumor_radius * tumor_radius )
            {
                Cell* pCell = create_cell( *pSW480 );
                pCell->assign_position( x, y, 0.0 );
                sw480_count++;
            }
            // 2. Anillo de Tejido Sano (200 um < r <= 360 um)
            else if( r_sq <= healthy_outer_radius * healthy_outer_radius )
            {
                Cell* pCell = create_cell( *pHealthy );
                pCell->assign_position( x, y, 0.0 );
                healthy_count++;
            }
        }
    }

    std::cout << "Tejido generado exitosamente:" << std::endl;
    std::cout << " - Celulas tumorales SW480: " << sw480_count << std::endl;
    std::cout << " - Celulas sanas (Healthy_Epithelial): " << healthy_count << std::endl;

    return;
}

void parasporin_ode_rule( Cell* pCell, Phenotype& phenotype, double dt )
{
    if( phenotype.death.dead == true )
    { return; }

    static int parasporin_idx = microenvironment.find_density_index("parasporin");
    double P_ext = pCell->nearest_density_vector()[parasporin_idx];

    static int R_free_idx = pCell->custom_data.find_variable_index("receptores_libres");
    static int PR_bound_idx = pCell->custom_data.find_variable_index("parasporina_unida");
    static int pores_idx = pCell->custom_data.find_variable_index("poros_activos");
    static int damage_idx = pCell->custom_data.find_variable_index("damage_acumulado");

    double R_libre = pCell->custom_data[R_free_idx];
    double PR = pCell->custom_data[PR_bound_idx];
    double poros = pCell->custom_data[pores_idx];
    double damage = pCell->custom_data[damage_idx];

    // Carga de parámetros biocinéticos GROMACS (500 ns MD)
    static double k_on = parameters.doubles("k_on");                    // 0.006 1/(nM*min)
    static double k_off = parameters.doubles("k_off");                  // 1.10 1/min
    static double n_stoich = parameters.doubles("poration_stoichiometry"); // 4.0
    static double k_pore = parameters.doubles("k_pore_formation");      // 0.05 1/min
    static double k_repair = parameters.doubles("k_repair");            // 0.01 1/min

    // 1. Cinética Ligando-Receptor
    double dPR_dt = (k_on * P_ext * R_libre) - (k_off * PR);

    // 2. Poración (Tetrámero cooperativo n=4)
    double PR_complex = std::pow(std::max(0.0, PR), n_stoich);
    double dPores_dt = (k_pore * PR_complex) - (k_repair * poros);

    // 3. Acumulación de Daño Lítico
    double dDamage_dt = 1.0 * poros;

    // Integración numérica (Pasos de Euler)
    PR += dPR_dt * dt;
    R_libre -= dPR_dt * dt;
    poros += dPores_dt * dt;
    damage += dDamage_dt * dt;

    // Restricciones físicas no negativas
    pCell->custom_data[R_free_idx] = std::max(0.0, R_libre);
    pCell->custom_data[PR_bound_idx] = std::max(0.0, PR);
    pCell->custom_data[pores_idx] = std::max(0.0, poros);
    pCell->custom_data[damage_idx] = std::max(0.0, damage);

    return;
}

void sw480_phenotype_rule( Cell* pCell, Phenotype& phenotype, double dt )
{
    if( phenotype.death.dead == true )
    { return; }

    static int damage_idx = pCell->custom_data.find_variable_index("damage_acumulado");
    double damage = pCell->custom_data[damage_idx];

    static double damage_threshold = parameters.doubles("damage_threshold");
    static int necrosis_index = phenotype.death.find_death_model_index("necrosis");

    // Muerte por lisis si el daño supera el umbral
    if( damage >= damage_threshold )
    {
        phenotype.death.rates[necrosis_index] = 0.1;
    }
    return;
}

void healthy_phenotype_rule( Cell* pCell, Phenotype& phenotype, double dt )
{
    if( phenotype.death.dead == true )
    { return; }

    static int damage_idx = pCell->custom_data.find_variable_index("damage_acumulado");
    double damage = pCell->custom_data[damage_idx];

    static double damage_threshold = parameters.doubles("damage_threshold");
    static int necrosis_index = phenotype.death.find_death_model_index("necrosis");

    if( damage >= damage_threshold )
    {
        phenotype.death.rates[necrosis_index] = 0.1;
    }
    return;
}
