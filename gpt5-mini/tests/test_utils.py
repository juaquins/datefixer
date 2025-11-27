from fdh import utils


def test_parse_date_iso():
    s = "2020-01-02 03:04:05"
    dt = utils.parse_date(s)
    assert dt.year == 2020


def test_infer_from_filename():
    name = "PXL_20200102_030405.jpg"
    dt = utils.infer_from_filename(name)
    assert dt is not None
