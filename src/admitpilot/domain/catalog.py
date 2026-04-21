"""Canonical admissions catalog for supported schools and programs."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field


def _normalize_token(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())


def _is_short_ascii_token(value: str) -> bool:
    return value.isascii() and value.isalnum() and len(value) <= 4


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

    def extract_school_codes_from_text(self, text: str) -> list[str]:
        if not text.strip():
            return []
        upper_text = text.upper()
        normalized_text = _normalize_token(text)
        matches: list[tuple[int, int, str]] = []
        for alias, code in self.school_aliases.items():
            if _is_short_ascii_token(alias):
                pattern = re.compile(
                    rf"(?<![A-Z0-9]){re.escape(alias)}(?![A-Z0-9])",
                    flags=re.IGNORECASE,
                )
                for match in pattern.finditer(upper_text):
                    matches.append((match.start(), -len(alias), code))
                continue
            idx = normalized_text.find(alias)
            if idx >= 0:
                matches.append((idx, -len(alias), code))
        ordered: list[str] = []
        seen: set[str] = set()
        for _, _, code in sorted(matches):
            if code in seen:
                continue
            ordered.append(code)
            seen.add(code)
        return ordered

    def extract_program_codes_from_text(
        self,
        text: str,
        school_code: str | None = None,
    ) -> list[str]:
        normalized_text = _normalize_token(text)
        if not normalized_text:
            return []
        upper_text = text.upper()
        allowed_programs = (
            set(self.supported_programs(school_code))
            if school_code is not None
            else set(self.program_aliases.values())
        )
        matches: list[tuple[int, int, int, str]] = []
        for alias, code in self.program_aliases.items():
            if code not in allowed_programs or not alias:
                continue
            normalized_code = _normalize_token(code)
            # Short aliases must be token-bounded to avoid false positives,
            # e.g. "AI" shouldn't match inside "AIS".
            if _is_short_ascii_token(alias) and alias != normalized_code:
                pattern = re.compile(
                    rf"(?<![A-Z0-9]){re.escape(alias)}(?![A-Z0-9])",
                    flags=re.IGNORECASE,
                )
                for match in pattern.finditer(upper_text):
                    matches.append((match.start(), -len(alias), match.start() + len(alias), code))
                continue
            if len(alias) < 4 and alias != normalized_code:
                continue
            start = normalized_text.find(alias)
            if start < 0:
                continue
            matches.append((start, -len(alias), start + len(alias), code))
        return self._ordered_unique_codes(matches)

    def has_program_intent(self, text: str) -> bool:
        lowered = text.lower()
        return any(
            marker in lowered
            for marker in (
                "master",
                "msc",
                "ms ",
                "ms-",
                "硕士",
                "项目",
                "program",
            )
        )

    def extract_program_hint(self, text: str) -> str:
        # Try to keep the user-mentioned program phrase for unsupported_program reporting.
        patterns = [
            re.compile(
                r"((?:master|msc)\s+(?:of|in)?\s*[a-z][a-z0-9&/\-\s]{2,80})",
                flags=re.IGNORECASE,
            ),
            re.compile(r"([A-Za-z][A-Za-z0-9&/\-\s]{1,40}硕士)"),
            re.compile(r"(硕士[A-Za-z0-9\u4e00-\u9fff&/\-\s]{1,30})"),
        ]
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                return " ".join(match.group(1).split()).strip(" ,.;，。；")
        return ""

    def program_display_name(self, school_code: str, program_code: str) -> str:
        school = self.get_school(school_code)
        normalized_program = self.normalize_program_code(program_code)
        if school is None or normalized_program is None:
            return program_code
        program = school.programs.get(normalized_program)
        if program is None:
            return normalized_program
        return program.display_name

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

    def _ordered_unique_codes(self, matches: list[tuple[int, int, int, str]]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        covered_spans: list[tuple[int, int]] = []
        for start, _, end, code in sorted(matches):
            if any(
                start >= covered_start and end <= covered_end
                for covered_start, covered_end in covered_spans
            ):
                continue
            if code in seen:
                continue
            ordered.append(code)
            seen.add(code)
            covered_spans.append((start, end))
        return ordered


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
            aliases=("MASTEROFTECHNOLOGYINARTIFICIALINTELLIGENCESYSTEMS", "AIS"),
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
        "新加坡国立大学": "NUS",
        "新国立": "NUS",
        "NTU": "NTU",
        "NANYANGTECHNOLOGICALUNIVERSITY": "NTU",
        "南洋理工大学": "NTU",
        "南洋理工": "NTU",
        "HKU": "HKU",
        "THEUNIVERSITYOFHONGKONG": "HKU",
        "UNIVERSITYOFHONGKONG": "HKU",
        "香港大学": "HKU",
        "港大": "HKU",
        "CUHK": "CUHK",
        "THECHINESEUNIVERSITYOFHONGKONG": "CUHK",
        "CHINESEUNIVERSITYOFHONGKONG": "CUHK",
        "香港中文大学": "CUHK",
        "港中文": "CUHK",
        "HKUST": "HKUST",
        "HONGKONGUNIVERSITYOFSCIENCEANDTECHNOLOGY": "HKUST",
        "THEHONGKONGUNIVERSITYOFSCIENCEANDTECHNOLOGY": "HKUST",
        "香港科技大学": "HKUST",
        "港科大": "HKUST",
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
