"""Curated official live sources for real AIE execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OfficialLiveSourceConfig:
    """Live official source URLs for one school/program pair."""

    school: str
    program: str
    requirements_url: str
    deadline_url: str


DEFAULT_LIVE_OFFICIAL_SOURCES: tuple[OfficialLiveSourceConfig, ...] = (
    OfficialLiveSourceConfig(
        school="HKU",
        program="MSCS",
        requirements_url="https://www.msc-cs.hku.hk/Admission/Requirements",
        deadline_url="https://www.msc-cs.hku.hk/Admission/Procedures",
    ),
    OfficialLiveSourceConfig(
        school="HKU",
        program="MDS",
        requirements_url="https://mdasc.cds.hku.hk/admissions/",
        deadline_url="https://mdasc.cds.hku.hk/admissions/",
    ),
    OfficialLiveSourceConfig(
        school="HKU",
        program="MECIC",
        requirements_url="https://www.ecom-icom.hku.hk/Admission/entrance_requirements",
        deadline_url="https://www.ecom-icom.hku.hk/Admission/application",
    ),
    OfficialLiveSourceConfig(
        school="HKU",
        program="MSFTDA",
        requirements_url="https://mscftda.cds.hku.hk/Admission/Requirements",
        deadline_url="https://mscftda.cds.hku.hk/Admission/Application",
    ),
    OfficialLiveSourceConfig(
        school="HKU",
        program="MSAI",
        requirements_url="https://www.mscai.hku.hk/admissions/",
        deadline_url="https://www.mscai.hku.hk/admissions/",
    ),
    OfficialLiveSourceConfig(
        school="CUHK",
        program="MSCS",
        requirements_url="https://msc.cse.cuhk.edu.hk/?lang=en&page_id=136",
        deadline_url="https://msc.cse.cuhk.edu.hk/?lang=en&page_id=90",
    ),
    OfficialLiveSourceConfig(
        school="CUHK",
        program="MSAI",
        requirements_url="https://mscai.erg.cuhk.edu.hk/admission",
        deadline_url="https://mscai.erg.cuhk.edu.hk/admission",
    ),
    OfficialLiveSourceConfig(
        school="CUHK",
        program="MSIE",
        requirements_url="https://msc.ie.cuhk.edu.hk/admission/",
        deadline_url="https://msc.ie.cuhk.edu.hk/admission/",
    ),
    OfficialLiveSourceConfig(
        school="CUHK",
        program="MSISTM",
        requirements_url="https://masters.bschool.cuhk.edu.hk/programmes/mscistm/admissions/",
        deadline_url="https://masters.bschool.cuhk.edu.hk/programmes/mscistm/admissions/",
    ),
    OfficialLiveSourceConfig(
        school="CUHK",
        program="MSELT",
        requirements_url="https://msc-eclt.se.cuhk.edu.hk/application/admission-criteria/",
        deadline_url="https://msc-eclt.se.cuhk.edu.hk/application/application-procedure/",
    ),
    OfficialLiveSourceConfig(
        school="CUHK",
        program="MSFT",
        requirements_url="https://fintech.erg.cuhk.edu.hk/admission/entry-requirements",
        deadline_url="https://fintech.erg.cuhk.edu.hk/admission/application-procedures-and-deadlines",
    ),
    OfficialLiveSourceConfig(
        school="HKUST",
        program="MSAI",
        requirements_url="https://seng.hkust.edu.hk/academics/taught-postgraduate/msc-ai",
        deadline_url="https://seng.hkust.edu.hk/academics/taught-postgraduate/msc-ai",
    ),
    OfficialLiveSourceConfig(
        school="HKUST",
        program="MSBDT",
        requirements_url="https://seng.hkust.edu.hk/academics/taught-postgraduate/msc-bdt",
        deadline_url="https://seng.hkust.edu.hk/academics/taught-postgraduate/msc-bdt",
    ),
    OfficialLiveSourceConfig(
        school="HKUST",
        program="MSIT",
        requirements_url="https://seng.hkust.edu.hk/academics/taught-postgraduate/msc-it",
        deadline_url="https://seng.hkust.edu.hk/academics/taught-postgraduate/msc-it",
    ),
    OfficialLiveSourceConfig(
        school="HKUST",
        program="MSDDM",
        requirements_url="https://msdm.hkust.edu.hk/",
        deadline_url="https://msdm.hkust.edu.hk/admission-procedure",
    ),
    # NUS live mode is limited to pages the current httpx-based fetcher can read
    # without JS execution or anti-bot challenges.
    OfficialLiveSourceConfig(
        school="NUS",
        program="MCOMP_CS",
        requirements_url="https://www.comp.nus.edu.sg/programmes/pg/mcs/admissions/",
        deadline_url="https://www.comp.nus.edu.sg/programmes/pg/mcs/application/",
    ),
    OfficialLiveSourceConfig(
        school="NUS",
        program="MCOMP_IS",
        requirements_url="https://www.comp.nus.edu.sg/programmes/pg/mis/admissions/",
        deadline_url="https://www.comp.nus.edu.sg/programmes/pg/mis/application/",
    ),
    OfficialLiveSourceConfig(
        school="NUS",
        program="MCOMP_ISEC",
        requirements_url="https://www.comp.nus.edu.sg/programmes/pg/misc/admissions/",
        deadline_url="https://www.comp.nus.edu.sg/programmes/pg/misc/application/",
    ),
    OfficialLiveSourceConfig(
        school="NUS",
        program="MCOMP_GENERAL",
        requirements_url="https://www.comp.nus.edu.sg/programmes/pg/mcomp-gen/admissions/",
        deadline_url="https://www.comp.nus.edu.sg/programmes/pg/mcomp-gen/application/",
    ),
    OfficialLiveSourceConfig(
        school="NUS",
        program="MCOMP_AI",
        requirements_url="https://www.comp.nus.edu.sg/programmes/pg/mcomp-ai/admissions/",
        deadline_url="https://www.comp.nus.edu.sg/programmes/pg/mcomp-ai/application/",
    ),
    OfficialLiveSourceConfig(
        school="NUS",
        program="MSDFT",
        requirements_url="https://www.comp.nus.edu.sg/programmes/pg/mdft/admissions/",
        deadline_url="https://www.comp.nus.edu.sg/programmes/pg/mdft/application/",
    ),
    OfficialLiveSourceConfig(
        school="NTU",
        program="MSAI",
        requirements_url=(
            "https://www.ntu.edu.sg/education/graduate-programme/"
            "master-of-science-in-artificial-intelligence"
        ),
        deadline_url=(
            "https://www.ntu.edu.sg/education/graduate-programme/"
            "master-of-science-in-artificial-intelligence"
        ),
    ),
    OfficialLiveSourceConfig(
        school="NTU",
        program="MCAAI",
        requirements_url=(
            "https://www.ntu.edu.sg/education/graduate-programme/"
            "master-of-computing-in-applied-ai-mcaai"
        ),
        deadline_url=(
            "https://www.ntu.edu.sg/education/graduate-programme/"
            "master-of-computing-in-applied-ai-mcaai"
        ),
    ),
    OfficialLiveSourceConfig(
        school="NTU",
        program="MSDS",
        requirements_url=(
            "https://www.ntu.edu.sg/education/graduate-programme/"
            "master-of-science-in-data-science-%28msds%29"
        ),
        deadline_url=(
            "https://www.ntu.edu.sg/education/graduate-programme/"
            "master-of-science-in-data-science-%28msds%29"
        ),
    ),
    OfficialLiveSourceConfig(
        school="NTU",
        program="MSCYBER",
        requirements_url=(
            "https://www.ntu.edu.sg/education/graduate-programme/"
            "master-of-science-in-cyber-security-%28mscs%29"
        ),
        deadline_url=(
            "https://www.ntu.edu.sg/education/graduate-programme/"
            "master-of-science-in-cyber-security-%28mscs%29"
        ),
    ),
    OfficialLiveSourceConfig(
        school="NTU",
        program="MSBT",
        requirements_url=(
            "https://www.ntu.edu.sg/computing/admissions/graduate-programmes/detail/"
            "master-of-science-in-blockchain"
        ),
        deadline_url=(
            "https://www.ntu.edu.sg/computing/admissions/graduate-programmes/detail/"
            "master-of-science-in-blockchain"
        ),
    ),
)
