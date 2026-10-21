"""Tests para app/xml_validator.py"""
import os

from app.xml_validator import validar_config


def test_valida_xml_ejemplo_repo(cfg_path):
    """El XML de ejemplo del repositorio debe ser válido."""
    resultado = validar_config(cfg_path)
    assert resultado["ok"] is True
    assert resultado["errores"] == []


def test_valida_archivo_inexistente(tmp_output_dir):
    """Un archivo que no existe debe devolver ok=False."""
    inexistente = os.path.join(tmp_output_dir, "no_existe.xml")
    resultado = validar_config(inexistente)
    assert resultado["ok"] is False
    assert len(resultado["errores"]) > 0


def test_valida_xml_mal_formado(tmp_output_dir):
    """Un XML mal formado debe detectarse."""
    mal = os.path.join(tmp_output_dir, "mal.xml")
    with open(mal, "w", encoding="utf-8") as f:
        f.write("<PhysiCell_settings><domain><x_min>0</x_min>")
    resultado = validar_config(mal)
    assert resultado["ok"] is False
    assert any("mal formado" in e.lower() for e in resultado["errores"])


def test_valida_xml_sin_secciones_requeridas(tmp_output_dir):
    """Un XML sin secciones requeridas debe fallar."""
    incompleto = os.path.join(tmp_output_dir, "incompleto.xml")
    with open(incompleto, "w", encoding="utf-8") as f:
        f.write("<PhysiCell_settings><overall><max_time>10</max_time></overall></PhysiCell_settings>")
    resultado = validar_config(incompleto)
    assert resultado["ok"] is False
    assert any("Falta seccion" in e for e in resultado["errores"])


def test_valida_xml_con_warnings_pero_ok(tmp_output_dir):
    """Un XML con secciones requeridas pero sin tags recomendados es válido con warnings."""
    minimal = os.path.join(tmp_output_dir, "minimal.xml")
    with open(minimal, "w", encoding="utf-8") as f:
        f.write("""<?xml version='1.0'?>
<PhysiCell_settings>
    <domain>
        <x_min>-500</x_min><x_max>500</x_max>
        <y_min>-500</y_min><y_max>500</y_max>
        <z_min>-10</z_min><z_max>10</z_max>
    </domain>
    <overall>
        <max_time units="min">7200</max_time>
    </overall>
    <microenvironment_setup>
        <variable name="substrate" ID="0">
            <physical_parameter_set>
                <diffusion_coefficient units="micron^2/min">100000.0</diffusion_coefficient>
                <decay_rate units="1/min">10</decay_rate>
            </physical_parameter_set>
        </variable>
    </microenvironment_setup>
    <cell_definitions>
        <cell_definition name="default">
            <phenotype></phenotype>
        </cell_definition>
    </cell_definitions>
</PhysiCell_settings>""")
    resultado = validar_config(minimal)
    # Tiene domain, overall, microenvironment_setup, cell_definitions -> ok=True
    # Pero falta max_time? No, lo tiene. Puede tener warnings por variable sin diffusion/decay? No, los tiene.
    assert resultado["ok"] is True
