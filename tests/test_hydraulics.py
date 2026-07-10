from core import hydraulics as hy

Q = 5.141621e-3   # m3/s
D = 0.0795        # m
L = 284.8
KS_PEAD = 0.007e-3


def test_velocity():
    assert abs(hy.velocity(Q, D) - 1.0358) < 1e-3


def test_colebrook_friction_factor():
    Re = 94251.33
    f = hy.friction_factor(Re, KS_PEAD / D)
    assert abs(f - 0.018591) < 2e-4


def test_friction_factor_laminar():
    assert abs(hy.friction_factor(1000, 0.001) - 64 / 1000) < 1e-9


def test_hf_darcy():
    V = hy.velocity(Q, D)
    hf = hy.hf_darcy(f=0.018591, L=L, D=D, V=V)
    assert abs(hf - 3.6419) < 5e-3


def test_hl_local():
    V = hy.velocity(Q, D)
    assert abs(hy.hl_local(14.6, V) - 14.6 * V**2 / (2 * 9.81)) < 1e-9


def test_reynolds():
    V = hy.velocity(Q, D)
    assert abs(hy.reynolds(V, D, nu=8.737e-7) - 94249) < 60
