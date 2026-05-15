export interface User {
  id: number;
  username: string;
  email?: string;
  native_language?: string;
  created_at?: string;
}

export interface LoginResponse {
  success: boolean;
  session_token?: string;
  user_id?: number;
  error?: string;
}

export interface MeResponse {
  success: boolean;
  user: User | null;
  error?: string;
}

export interface CourseLanguage {
  code: string;
  name: string;
  native_name?: string;
}

export interface CoursesResponse {
  success: boolean;
  languages: CourseLanguage[];
}

export interface CustomGroupSummary {
  id: number;
  name: string;
  language?: string;
  level_count?: number;
  completed_levels?: number;
  topic?: string;
}

export interface GroupsSummaryResponse {
  success: boolean;
  groups?: CustomGroupSummary[];
}

export interface WordItem {
  id?: number;
  word_id?: number;
  word: string;
  translation?: string;
  familiarity?: number;
  language?: string;
}

export interface WordsLearningResponse {
  success: boolean;
  words?: WordItem[];
  total?: number;
}

export interface MarketplaceGroup {
  id: number;
  name?: string;
  group_name?: string;
  description?: string;
  context_description?: string;
  language?: string;
  level_count?: number;
  num_levels?: number;
  author_name?: string;
}

export interface MarketplaceResponse {
  success: boolean;
  groups?: MarketplaceGroup[];
  total?: number;
  page?: number;
}
