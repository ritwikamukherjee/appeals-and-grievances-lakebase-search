export interface Result {
  case_id: string;
  service_category: string | null;
  denial_reason_code: string | null;
  denial_reason_desc: string | null;
  cpt_hcpcs_code: string | null;
  icd10_code: string | null;
  disposition: string | null;
  plan_name: string;
  line_of_business: string | null;
  member_id: string | null;
  filed_date: string | null;
  narrative: string;
  score: number | null;
  score_label: string;
}

export interface SearchResponse {
  vector: Result[];
  bm25: Result[];
  hybrid: Result[];
  concepts: string[];
  error?: string;
}

export async function search(
  q: string,
  kw: string,
  limit: number
): Promise<SearchResponse> {
  const params = new URLSearchParams({
    q,
    kw,
    limit: String(limit),
    mode: "all",
  });
  const res = await fetch(`/api/search?${params.toString()}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data as SearchResponse;
}
