"""Canonical admissions catalog for supported schools and programs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


def _normalize_token(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())


@dataclass(frozen=True, slots=True)
class ProgramCatalogEntry:
    """Program-level catalog metadata."""

    code: str
    display_name: str
    slug: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SchoolCatalogEntry:
    """School-level catalog metadata."""

    code: str
    display_name: str
    region: str
    official_domains: tuple[str, ...]
    default_page_types: tuple[str, ...]
    programs: dict[str, ProgramCatalogEntry] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AdmissionsCatalog:
    """Single source of truth for supported schools and programs."""

    schools: dict[str, SchoolCatalogEntry]
    school_aliases: dict[str, str]
    program_aliases: dict[str, str]
    default_program_by_school: dict[str, str]

    def all_school_codes(self) -> tuple[str, ...]:
        return tuple(self.schools.keys())

    def get_school(self, school_code: str) -> SchoolCatalogEntry | None:
        normalized = self.normalize_school_code(school_code)
        if normalized is None:
            return None
        return self.schools.get(normalized)

    def normalize_school_code(self, school_code: str) -> str | None:
        normalized = _normalize_token(school_code)
        if not normalized:
            return None
        return self.school_aliases.get(normalized)

    def normalize_program_code(self, program_code: str) -> str | None:
        normalized = _normalize_token(program_code)
        if not normalized:
            return None
        return self.program_aliases.get(normalized)

    def supported_programs(self, school_code: str) -> tuple[str, ...]:
        school = self.get_school(school_code)
        if school is None:
            return ()
        return tuple(school.programs.keys())

    def default_program_portfolio(
        self,
        schools: Iterable[str] | None = None,
    ) -> dict[str, str]:
        scoped_schools = self.normalize_school_scope(schools)
        portfolio: dict[str, str] = {}
        for school in scoped_schools:
            program = self.default_program_by_school.get(school)
            if program and self.is_supported_program(school, program):
                portfolio[school] = program
        return portfolio

    def default_page_types(
        self,
        school_code: str,
        program_code: str | None = None,
    ) -> tuple[str, ...]:
        del program_code
        school = self.get_school(school_code)
        if school is None:
            return ()
        return school.default_page_types

    def official_domains(self, school_code: str) -> tuple[str, ...]:
        school = self.get_school(school_code)
        if school is None:
            return ()
        return school.official_domains

    def is_supported_program(self, school_code: str, program_code: str) -> bool:
        school = self.get_school(school_code)
        normalized_program = self.normalize_program_code(program_code)
        if school is None or normalized_program is None:
            return False
        return normalized_program in school.programs

    def normalize_school_scope(self, schools: Iterable[str] | None) -> list[str]:
        if schools is None:
            return list(self.all_school_codes())
        resolved: list[str] = []
        seen: set[str] = set()
        for item in schools:
            normalized = self.normalize_school_code(item)
            if normalized is None or normalized in seen:
                continue
            resolved.append(normalized)
            seen.add(normalized)
        return resolved or list(self.all_school_codes())

    def build_page_url(
        self, school_code: str, program_code: str, cycle: str, page_type: str
    ) -> str:
        school = self.get_school(school_code)
        normalized_program = self.normalize_program_code(program_code)
        if school is None or normalized_program is None:
            raise ValueError("unsupported school/program")
        program = school.programs.get(normalized_program)
        if program is None:
            raise ValueError("unsupported school/program")
        primary_domain = school.official_domains[0]
        return (
            f"https://{primary_domain}/admissions/"
            f"{program.slug}/{cycle}/{page_type}.html"
        )


def _build_catalog() -> AdmissionsCatalog:
    program_entries = {
        "MSCS": ProgramCatalogEntry(
            code="MSCS",
            display_name="Master of Science in Computer Science",
            slug="mscs",
            aliases=(
                "COMPUTERSCIENCE",
                "MSINCOMPUTERSCIENCE",
                "MASTEROFCOMPUTERSCIENCE",
                "CS",
            ),
        ),
        "MSAI": ProgramCatalogEntry(
            code="MSAI",
            display_name="Master of Science in Artificial Intelligence",
            slug="msai",
            aliases=("ARTIFICIALINTELLIGENCE", "AI", "MSINAI"),
        ),
        "MDS": ProgramCatalogEntry(
            code="MDS",
            display_name="Master of Data Science",
            slug="mds",
            aliases=("DATASCIENCE",),
        ),
        "MECIC": ProgramCatalogEntry(
            code="MECIC",
            display_name="Master of Science in Electronic Commerce and Internet Computing",
            slug="mecic",
            aliases=("ELECTRONICCOMMERCEANDINTERNETCOMPUTING",),
        ),
        "MSFTDA": ProgramCatalogEntry(
            code="MSFTDA",
            display_name="Master of Science in Financial Technology and Data Analytics",
            slug="msftda",
            aliases=("FINANCIALTECHNOLOGYANDDATAANALYTICS",),
        ),
        "MSIE": ProgramCatalogEntry(
            code="MSIE",
            display_name="MSc in Information Engineering",
            slug="msie",
            aliases=("INFORMATIONENGINEERING",),
        ),
        "MSISTM": ProgramCatalogEntry(
            code="MSISTM",
            display_name="MSc in Information Science and Technology Management",
            slug="msistm",
            aliases=("INFORMATIONSCIENCEANDTECHNOLOGYMANAGEMENT",),
        ),
        "MSELT": ProgramCatalogEntry(
            code="MSELT",
            display_name="MSc in E-Commerce and Logistics Technologies",
            slug="mselt",
            aliases=("ECOMMERCEANDLOGISTICSTECHNOLOGIES",),
        ),
        "MSFT": ProgramCatalogEntry(
            code="MSFT",
            display_name="MSc in Financial Technology",
            slug="msft",
            aliases=("FINANCIALTECHNOLOGY",),
        ),
        "MSBDT": ProgramCatalogEntry(
            code="MSBDT",
            display_name="MSc in Big Data Technology",
            slug="msbdt",
            aliases=("BIGDATATECHNOLOGY",),
        ),
        "MSIT": ProgramCatalogEntry(
            code="MSIT",
            display_name="MSc in Information Technology",
            slug="msit",
            aliases=("INFORMATIONTECHNOLOGY",),
        ),
        "MSDDM": ProgramCatalogEntry(
            code="MSDDM",
            display_name="MSc in Data-Driven Modeling",
            slug="msddm",
            aliases=("DATADRIVENMODELING",),
        ),
        "MCOMP_CS": ProgramCatalogEntry(
            code="MCOMP_CS",
            display_name="Master of Computing (Computer Science Specialisation)",
            slug="mcomp-cs",
            aliases=("MASTEROFCOMPUTINGCOMPUTERSCIENCESPECIALISATION", "MCOMPCS"),
        ),
        "MCOMP_IS": ProgramCatalogEntry(
            code="MCOMP_IS",
            display_name="Master of Computing (Information Systems Specialisation)",
            slug="mcomp-is",
            aliases=("MASTEROFCOMPUTINGINFORMATIONSYSTEMSSPECIALISATION", "MCOMPIS"),
        ),
        "MCOMP_ISEC": ProgramCatalogEntry(
            code="MCOMP_ISEC",
            display_name="Master of Computing (Infocomm Security Specialisation)",
            slug="mcomp-isec",
            aliases=(
                "MASTEROFCOMPUTINGINFOCOMMSECURITYSPECIALISATION",
                "MCOMPINFOCOMMSECURITY",
            ),
        ),
        "MCOMP_GENERAL": ProgramCatalogEntry(
            code="MCOMP_GENERAL",
            display_name="Master of Computing (General Track)",
            slug="mcomp-general",
            aliases=("MASTEROFCOMPUTINGGENERALTRACK", "MCOMPGENERAL"),
        ),
        "MCOMP_AI": ProgramCatalogEntry(
            code="MCOMP_AI",
            display_name="Master of Computing in Artificial Intelligence",
            slug="mcomp-ai",
            aliases=("MASTEROFCOMPUTINGINARTIFICIALINTELLIGENCE",),
        ),
        "MSDFT": ProgramCatalogEntry(
            code="MSDFT",
            display_name="Master of Science in Digital FinTech",
            slug="ms-digital-fintech",
            aliases=("DIGITALFINTECH",),
        ),
        "MSBA": ProgramCatalogEntry(
            code="MSBA",
            display_name="Master of Science in Business Analytics",
            slug="ms-business-analytics",
            aliases=("BUSINESSANALYTICS",),
        ),
        "MTECH_AIS": ProgramCatalogEntry(
            code="MTECH_AIS",
            display_name="Master of Technology in Artificial Intelligence Systems",
            slug="mtech-ais",
            aliases=("MASTEROFTECHNOLOGYINARTIFICIALINTELLIGENCESYSTEMS",),
        ),
        "MTECH_SE": ProgramCatalogEntry(
            code="MTECH_SE",
            display_name="Master of Technology in Software Engineering",
            slug="mtech-se",
            aliases=("SOFTWAREENGINEERING",),
        ),
        "MTECH_EBA": ProgramCatalogEntry(
            code="MTECH_EBA",
            display_name="Master of Technology in Enterprise Business Analytics",
            slug="mtech-eba",
            aliases=("ENTERPRISEBUSINESSANALYTICS",),
        ),
        "MTECH_DL": ProgramCatalogEntry(
            code="MTECH_DL",
            display_name="Master of Technology in Digital Leadership",
            slug="mtech-dl",
            aliases=("DIGITALLEADERSHIP",),
        ),
        "MS_AIFS": ProgramCatalogEntry(
            code="MS_AIFS",
            display_name="Master of Science (AI for Science)",
            slug="ms-ai-for-science",
            aliases=("AIFORSCIENCE",),
        ),
        "MS_AII": ProgramCatalogEntry(
            code="MS_AII",
            display_name="Master of Science (Artificial Intelligence & Innovation)",
            slug="ms-ai-innovation",
            aliases=("ARTIFICIALINTELLIGENCEINNOVATION",),
        ),
        "EM_AIDT": ProgramCatalogEntry(
            code="EM_AIDT",
            display_name="Executive Master in AI & Digital Transformation",
            slug="executive-master-ai-digital-transformation",
            aliases=("EXECUTIVEMASTERINAIDIGITALTRANSFORMATION",),
        ),
        "MCAAI": ProgramCatalogEntry(
            code="MCAAI",
            display_name="Master of Computing in Applied AI",
            slug="mcaai",
            aliases=(
                "MASTEROFCOMPUTINGINAPPLIEDAI",
                "MASTEROFCOMPUTINGINAPPLIEDAIMCAAI",
            ),
        ),
        "MSDS": ProgramCatalogEntry(
            code="MSDS",
            display_name="Master of Science in Data Science",
            slug="msds",
            aliases=("DATASCIENCE", "MSINDATASCIENCE"),
        ),
        "MSCYBER": ProgramCatalogEntry(
            code="MSCYBER",
            display_name="Master of Science in Cyber Security (MSCS)",
            slug="ms-cyber-security",
            aliases=("CYBERSECURITY", "MASTEROFSCIENCEINCYBERSECURITY"),
        ),
        "MSBT": ProgramCatalogEntry(
            code="MSBT",
            display_name="Master of Science in Blockchain Technology",
            slug="ms-blockchain-technology",
            aliases=("BLOCKCHAINTECHNOLOGY",),
        ),
    }

    def school_programs(*codes: str) -> dict[str, ProgramCatalogEntry]:
        return {code: program_entries[code] for code in codes}

    schools = {
        "NUS": SchoolCatalogEntry(
            code="NUS",
            display_name="National University of Singapore",
            region="Singapore",
            official_domains=("nus.edu.sg", "www.nus.edu.sg"),
            default_page_types=("requirements", "deadline"),
            programs=school_programs(
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
            ),
        ),
        "NTU": SchoolCatalogEntry(
            code="NTU",
            display_name="Nanyang Technological University",
            region="Singapore",
            official_domains=("ntu.edu.sg", "www.ntu.edu.sg"),
            default_page_types=("requirements", "deadline"),
            programs=school_programs("MSCS", "MCAAI", "MSAI", "MSDS", "MSCYBER", "MSBT"),
        ),
        "HKU": SchoolCatalogEntry(
            code="HKU",
            display_name="The University of Hong Kong",
            region="Hong Kong",
            official_domains=("hku.hk", "www.hku.hk"),
            default_page_types=("requirements", "deadline"),
            programs=school_programs("MSCS", "MDS", "MECIC", "MSFTDA", "MSAI"),
        ),
        "CUHK": SchoolCatalogEntry(
            code="CUHK",
            display_name="The Chinese University of Hong Kong",
            region="Hong Kong",
            official_domains=("cuhk.edu.hk", "www.cuhk.edu.hk"),
            default_page_types=("requirements", "deadline"),
            programs=school_programs("MSCS", "MSAI", "MSIE", "MSISTM", "MSELT", "MSFT"),
        ),
        "HKUST": SchoolCatalogEntry(
            code="HKUST",
            display_name="The Hong Kong University of Science and Technology",
            region="Hong Kong",
            official_domains=("ust.hk", "www.ust.hk", "hkust.edu.hk", "seng.hkust.edu.hk"),
            default_page_types=("requirements", "deadline"),
            programs=school_programs("MSCS", "MSAI", "MSBDT", "MSIT", "MSDDM"),
        ),
    }

    school_aliases = {
        "NUS": "NUS",
        "NATIONALUNIVERSITYOFSINGAPORE": "NUS",
        "NTU": "NTU",
        "NANYANGTECHNOLOGICALUNIVERSITY": "NTU",
        "HKU": "HKU",
        "THEUNIVERSITYOFHONGKONG": "HKU",
        "UNIVERSITYOFHONGKONG": "HKU",
        "CUHK": "CUHK",
        "THECHINESEUNIVERSITYOFHONGKONG": "CUHK",
        "CHINESEUNIVERSITYOFHONGKONG": "CUHK",
        "HKUST": "HKUST",
        "HONGKONGUNIVERSITYOFSCIENCEANDTECHNOLOGY": "HKUST",
        "THEHONGKONGUNIVERSITYOFSCIENCEANDTECHNOLOGY": "HKUST",
    }
    program_aliases = {
        "MSCS": "MSCS",
        "MSAI": "MSAI",
        "MDS": "MDS",
        "MECIC": "MECIC",
        "MSFTDA": "MSFTDA",
        "MSIE": "MSIE",
        "MSISTM": "MSISTM",
        "MSELT": "MSELT",
        "MSFT": "MSFT",
        "MSBDT": "MSBDT",
        "MSIT": "MSIT",
        "MSDDM": "MSDDM",
        "MCOMPCS": "MCOMP_CS",
        "MCOMPIS": "MCOMP_IS",
        "MCOMPISEC": "MCOMP_ISEC",
        "MCOMPGENERAL": "MCOMP_GENERAL",
        "MCOMPAI": "MCOMP_AI",
        "MSDFT": "MSDFT",
        "MSBA": "MSBA",
        "MTECHAIS": "MTECH_AIS",
        "MTECHSE": "MTECH_SE",
        "MTECHEBA": "MTECH_EBA",
        "MTECHDL": "MTECH_DL",
        "MSAIFS": "MS_AIFS",
        "MSAII": "MS_AII",
        "EMAIDT": "EM_AIDT",
        "MCAAI": "MCAAI",
        "MSDS": "MSDS",
        "MSCYBER": "MSCYBER",
        "MSBT": "MSBT",
    }
    for program in program_entries.values():
        for alias in program.aliases:
            program_aliases[_normalize_token(alias)] = program.code
        program_aliases[_normalize_token(program.display_name)] = program.code
        program_aliases[_normalize_token(program.code)] = program.code
    return AdmissionsCatalog(
        schools=schools,
        school_aliases=school_aliases,
        program_aliases=program_aliases,
        default_program_by_school={
            "NUS": "MCOMP_CS",
            "NTU": "MSAI",
            "HKU": "MSCS",
            "CUHK": "MSCS",
            "HKUST": "MSIT",
        },
    )


DEFAULT_ADMISSIONS_CATALOG = _build_catalog()
