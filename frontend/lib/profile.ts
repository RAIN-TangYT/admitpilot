import type { AdmitPilotRequest, MissingProfileField, UserProfile } from "./types";

const FIELD_SPECS: Record<string, MissingProfileField> = {
  degree_level: {
    key: "degree_level",
    label: "Degree level",
    required: true,
    help_text: "Select the applicant's current degree level."
  },
  major_interest: {
    key: "major_interest",
    label: "Major interest",
    required: true,
    help_text: "Enter the intended academic direction."
  },
  target_schools: {
    key: "target_schools",
    label: "Target schools",
    required: true,
    help_text: "Select at least one target school."
  },
  target_programs: {
    key: "target_programs",
    label: "Target programs",
    required: true,
    help_text: "Select at least one target program."
  },
  "academic_metrics.gpa": {
    key: "academic_metrics.gpa",
    label: "GPA",
    required: true,
    help_text: "Enter a GPA greater than 0."
  },
  language_scores: {
    key: "language_scores",
    label: "Language score",
    required: true,
    help_text: "Enter an IELTS, TOEFL, or TOEFL iBT score."
  },
  experiences: {
    key: "experiences",
    label: "Experience materials",
    required: true,
    help_text: "Add at least one experience for essays and interviews."
  }
};

const FIELD_ORDER = Object.keys(FIELD_SPECS);

export function createEmptyRequest(): AdmitPilotRequest {
  return {
    user_query: "I need school selection, timeline planning, and document preparation for the 2026 application cycle.",
    profile: {
      name: "",
      degree_level: "",
      major_interest: "",
      target_regions: [],
      academic_metrics: { gpa: "" },
      language_scores: { ielts: "" },
      experiences: [],
      target_schools: [],
      target_programs: [],
      risk_preference: "balanced"
    },
    constraints: {
      cycle: "2026",
      timezone: "Asia/Shanghai",
      timeline_weeks: 8,
      target_schools: [],
      target_program_by_school: {},
      user_artifacts: []
    }
  };
}

export function normalizeRequest(payload: AdmitPilotRequest): AdmitPilotRequest {
  const empty = createEmptyRequest();
  return {
    ...empty,
    ...payload,
    profile: {
      ...empty.profile,
      ...payload.profile,
      academic_metrics: {
        ...empty.profile.academic_metrics,
        ...(payload.profile?.academic_metrics ?? {})
      },
      language_scores: {
        ...empty.profile.language_scores,
        ...(payload.profile?.language_scores ?? {})
      },
      experiences: payload.profile?.experiences ?? [],
      target_schools: payload.profile?.target_schools ?? [],
      target_programs: payload.profile?.target_programs ?? []
    },
    constraints: {
      ...empty.constraints,
      ...payload.constraints,
      target_schools: payload.constraints?.target_schools ?? [],
      target_program_by_school: payload.constraints?.target_program_by_school ?? {},
      user_artifacts: payload.constraints?.user_artifacts ?? []
    }
  };
}

export function validateProfile(profile: UserProfile): MissingProfileField[] {
  const missing: string[] = [];
  if (!profile.degree_level.trim()) {
    missing.push("degree_level");
  }
  if (!profile.major_interest.trim()) {
    missing.push("major_interest");
  }
  if (!profile.target_schools.length) {
    missing.push("target_schools");
  }
  if (!profile.target_programs.length) {
    missing.push("target_programs");
  }
  if (!isPositiveNumber(profile.academic_metrics.gpa)) {
    missing.push("academic_metrics.gpa");
  }
  if (!hasLanguageScore(profile.language_scores)) {
    missing.push("language_scores");
  }
  if (!profile.experiences.length) {
    missing.push("experiences");
  }
  const order = new Map(FIELD_ORDER.map((key, index) => [key, index]));
  return missing
    .sort((left, right) => (order.get(left) ?? 0) - (order.get(right) ?? 0))
    .map((key) => FIELD_SPECS[key]);
}

export function splitExperienceText(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function experienceText(profile: UserProfile): string {
  return profile.experiences.join("\n");
}

function isPositiveNumber(value: unknown): boolean {
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric > 0;
}

function hasLanguageScore(scores: Record<string, unknown>): boolean {
  return ["ielts", "toefl", "toefl_ibt"].some((key) => isPositiveNumber(scores[key]));
}
