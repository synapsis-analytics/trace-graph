import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, unwrapLenses, type GraphParams, type NeighbourhoodParams, type ClaimsParams, type ObjectsParams } from "@/lib/api";
import type { Lens } from "@/lib/types";

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 30_000 });
}

export function useStats() {
  return useQuery({ queryKey: ["stats"], queryFn: api.stats });
}

export function useLenses() {
  return useQuery<Lens[]>({
    queryKey: ["lenses"],
    queryFn: async () => unwrapLenses(await api.lenses()),
    staleTime: Infinity,
  });
}

export function useGraph(params: GraphParams, enabled = true) {
  return useQuery({
    queryKey: ["graph", params],
    queryFn: () => api.graph(params),
    enabled,
  });
}

export function useNeighbourhood(id: string | null, params: NeighbourhoodParams, enabled = true) {
  return useQuery({
    queryKey: ["neighbourhood", id, params],
    queryFn: () => api.neighbourhood(id as string, params),
    enabled: Boolean(id) && enabled,
  });
}

export function useObject(id: string | null) {
  return useQuery({
    queryKey: ["object", id],
    queryFn: () => api.object(id as string),
    enabled: Boolean(id),
  });
}

export function useObjects(params: ObjectsParams, enabled = true) {
  return useQuery({
    queryKey: ["objects", params],
    queryFn: () => api.objects(params),
    enabled,
  });
}

export function useCoverage(layer: number | "all") {
  return useQuery({
    queryKey: ["coverage", layer],
    queryFn: () => api.coverage(layer === "all" ? undefined : layer),
  });
}

export function useClaims(params: ClaimsParams) {
  return useQuery({ queryKey: ["claims", params], queryFn: () => api.claims(params) });
}

export function usePath(from: string | null, to: string | null, lens: string | undefined) {
  return useQuery({
    queryKey: ["path", from, to, lens],
    queryFn: () => api.path(from as string, to as string, lens),
    enabled: Boolean(from && to),
  });
}

/** Debounced value helper — every search box in the app uses it. */
export function useDebounced<T>(value: T, ms = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}
