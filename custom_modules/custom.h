#ifndef __CUSTOM_H__
#define __CUSTOM_H__

#include "../core/PhysiCell.h"
#include "../modules/PhysiCell_standard_models.h"

using namespace BioFVM;
using namespace PhysiCell;

// Configuración de definiciones celulares y tejido
void create_cell_types( void );
void setup_tissue( void );
void setup_microenvironment( void );

// Reglas de fenotipo para células SW480 (Cáncer) y Healthy_Epithelial (Sana)
void sw480_phenotype_rule( Cell* pCell, Phenotype& phenotype, double dt );
void healthy_phenotype_rule( Cell* pCell, Phenotype& phenotype, double dt );

// Regla cinético-médica de ODEs para la parasporina
void parasporin_ode_rule( Cell* pCell, Phenotype& phenotype, double dt );

#endif
