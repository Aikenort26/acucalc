from core import population as pop, report_figs as rf
from core.curves import fit_curve
from core.project import TankSpec
from tests.test_population import CENSO

FACTORES = [0.6,0.7,0.8,0.9,1,1.2,1.6,1.2,1,1.1,1.1,1.2,1.1,1.1,1,1.1,1.2,1.1,0.9,0.9,0.9,0.8,0.8,0.7]
BOMBEO = [1 if 5 <= h <= 14 else 0 for h in range(24)]


def _save_ok(fig, tmp_path, name):
    f = tmp_path / f"{name}.png"
    fig.savefig(f, dpi=100)
    assert f.exists() and f.stat().st_size > 1000


def test_fig_poblacion_y_metodos(tmp_path):
    rates = pop.growth_rates(CENSO)
    proj = pop.project(1400, 2026, 2051, rates, 0.005)
    _save_ok(rf.fig_poblacion(proj, "res0844", flotante_pct=0.1), tmp_path, "pob")
    _save_ok(rf.fig_metodos(proj.deviations, pop.suggest_method(proj)), tmp_path, "met")


def test_fig_caudales(tmp_path):
    serie = [(2026 + i, 1.4 + i * 0.01, 1.8 + i * 0.013, 2.9 + i * 0.02)
             for i in range(26)]
    _save_ok(rf.fig_caudales(serie), tmp_path, "caud")


def test_fig_balance(tmp_path):
    _save_ok(rf.fig_balance([1] * 24, BOMBEO, FACTORES), tmp_path, "bal")


def test_fig_sistema(tmp_path):
    fit = fit_curve([(2, 33), (5, 30), (8, 22), (10, 14)], 2)
    sys_lps = [(q / 10, 10 + 0.15 * (q / 10) ** 2) for q in range(0, 120)]
    bombas = [{"nombre": "Bomba A", "fit": fit, "op": (7.5, 18.4)}]
    _save_ok(rf.fig_sistema(sys_lps, bombas, qb_lps=5.1, hd=17.0, titulo="Sistema 1"),
             tmp_path, "sis")


def test_fig_esquema_sin_tanques(tmp_path):
    _save_ok(rf.fig_esquema([{"tipo_bomba": "superficie"}], []), tmp_path, "esq_sin_tk")


def test_fig_esquema_pozo_dos_tanques(tmp_path):
    tanques = [
        TankSpec("Tanque bajo", "bajo", "rectangular", 30, 2.5, 1.5,
                 tipo_constructivo="semienterrado", cantidad=1),
        TankSpec("Tanque elevado", "elevado", "circular", 110, 2.5, 1.0,
                 tipo_constructivo="elevado", cantidad=2),
    ]
    sistemas = [{"tipo_bomba": "sumergible"}, {"tipo_bomba": "superficie"}]
    _save_ok(rf.fig_esquema(sistemas, tanques), tmp_path, "esq_pozo_2tk")


def test_fig_esquema_todos_los_tipos_constructivos(tmp_path):
    for tipo in ("superficial", "enterrado", "semienterrado", "elevado"):
        tanques = [TankSpec("T", "bajo", "circular", 50, 2.5, 1.0,
                            tipo_constructivo=tipo)]
        _save_ok(rf.fig_esquema([{"tipo_bomba": "superficie"}], tanques),
                 tmp_path, f"esq_{tipo}")
