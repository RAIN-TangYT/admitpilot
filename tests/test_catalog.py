from admitpilot.domain.catalog import DEFAULT_ADMISSIONS_CATALOG


def test_catalog_normalizes_school_codes() -> None:
    catalog = DEFAULT_ADMISSIONS_CATALOG

    assert catalog.normalize_school_code("hkust") == "HKUST"
    assert catalog.normalize_school_code("National University of Singapore") == "NUS"
    assert catalog.normalize_program_code("Computer Science") == "MSCS"
    assert catalog.normalize_program_code("Master of Data Science") == "MDS"
    assert (
        catalog.normalize_program_code("Master of Computing (Computer Science Specialisation)")
        == "MCOMP_CS"
    )
    assert (
        catalog.normalize_program_code("Master of Science in Cyber Security (MSCS)")
        == "MSCYBER"
    )


def test_catalog_filters_invalid_schools() -> None:
    catalog = DEFAULT_ADMISSIONS_CATALOG

    scoped = catalog.normalize_school_scope(["mit", "hkust", "ntu", "HKUST"])

    assert scoped == ["HKUST", "NTU"]


def test_catalog_returns_supported_programs_and_page_types() -> None:
    catalog = DEFAULT_ADMISSIONS_CATALOG

    assert catalog.supported_programs("HKU") == ("MSCS", "MDS", "MECIC", "MSFTDA", "MSAI")
    assert catalog.supported_programs("CUHK") == (
        "MSCS",
        "MSAI",
        "MSIE",
        "MSISTM",
        "MSELT",
        "MSFT",
    )
    assert catalog.supported_programs("HKUST") == ("MSCS", "MSAI", "MSBDT", "MSIT", "MSDDM")
    assert catalog.supported_programs("NTU") == (
        "MSCS",
        "MCAAI",
        "MSAI",
        "MSDS",
        "MSCYBER",
        "MSBT",
    )
    assert catalog.default_page_types("HKUST", "MSAI") == ("requirements", "deadline")
    assert catalog.build_page_url("HKUST", "MSAI", "2026", "requirements").startswith(
        "https://ust.hk/"
    )


def test_catalog_returns_full_nus_program_scope() -> None:
    catalog = DEFAULT_ADMISSIONS_CATALOG

    assert catalog.supported_programs("NUS") == (
        "MSCS",
        "MSAI",
        "MCOMP_CS",
        "MCOMP_IS",
        "MCOMP_ISEC",
        "MCOMP_GENERAL",
        "MCOMP_AI",
        "MSDFT",
        "MSBA",
        "MTECH_AIS",
        "MTECH_SE",
        "MTECH_EBA",
        "MTECH_DL",
        "MS_AIFS",
        "MS_AII",
        "EM_AIDT",
    )


def test_catalog_returns_runtime_default_program_portfolio() -> None:
    catalog = DEFAULT_ADMISSIONS_CATALOG

    assert catalog.default_program_portfolio(["NUS", "NTU", "HKU", "CUHK", "HKUST"]) == {
        "NUS": "MCOMP_CS",
        "NTU": "MSAI",
        "HKU": "MSCS",
        "CUHK": "MSCS",
        "HKUST": "MSIT",
    }
