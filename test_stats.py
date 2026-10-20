import sys, os
sys.path.insert(0, '.')
import sqlite3
from app.nucleo import get_db_path
from app.reportes import generar_reporte_html
c = sqlite3.connect(get_db_path())
cur = c.cursor()
cur.execute(
    "INSERT INTO experiments (title, description, tags, config_xml_path) VALUES (?,?,?,?)",
    ("Analisis-test", "Test estadistica", "test",
     r"C:\Users\PC\Downloads\gestor_physicell\gestor_physicell\PhysiCell\config\PhysiCell_settings.xml"))
eid = cur.lastrowid
cur.execute(
    "INSERT INTO runs (experiment_id, run_number, status, start_time, end_time, output_dir) VALUES (?,?,?,?,?,?)",
    (eid, 1, "completed", "2026-10-17T08:00:00", "2026-10-17T08:01:00",
     r"C:\Users\PC\Downloads\gestor_physicell\gestor_physicell\PhysiCell\output"))
c.commit()
c.close()
out = os.path.join(os.path.dirname(get_db_path()), f'exp_{eid}', 'reporte.html')
print(generar_reporte_html(eid, get_db_path(), out))
h = open(out, encoding='utf-8').read()
import re
for m in re.findall(r'<h[12]>(.*?)</h[12]>', h):
    print('-', m[:70])
# limpiar test
c = sqlite3.connect(get_db_path())
c.execute("DELETE FROM runs WHERE experiment_id=?", (eid,))
c.execute("DELETE FROM experiments WHERE id=?", (eid,))
c.commit()
c.close()
print('TEST LIMPIO')
