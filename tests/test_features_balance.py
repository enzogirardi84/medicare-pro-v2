from features.balance import formato_shift_ml, totales_balance_hidrico_ml


def test_totales_balance_hidrico_ml():
    ing, egr, bal = totales_balance_hidrico_ml(i_oral=100, i_par=50, e_orina=80, e_dren=20, e_perd=10)
    assert ing == 150
    assert egr == 110
    assert bal == 40


def test_formato_shift_ml():
    assert formato_shift_ml(5) == "+5 ml"
    assert formato_shift_ml(-3) == "-3 ml"
    assert formato_shift_ml(0) == "0 ml"
