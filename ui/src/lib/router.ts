import * as React from "react";

/** Hash routes keep the server simple: every page is "/", and state lives after the "#". */
export interface Location { page: string; params: URLSearchParams }

function parse(): Location {
  const raw = location.hash.replace(/^#\/?/, "");
  const [page, query = ""] = raw.split("?");
  return { page: page || "overview", params: new URLSearchParams(query) };
}

export function useLocation(): Location {
  const [loc, setLoc] = React.useState(parse);
  React.useEffect(() => {
    const on = () => setLoc(parse());
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);
  return loc;
}

export function href(page: string, params?: Record<string, string>) {
  const q = params ? new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString() : "";
  return `#/${page}${q ? `?${q}` : ""}`;
}

export function navigate(page: string, params?: Record<string, string>) {
  location.hash = href(page, params);
}

/** Replaces the query of the current page without adding history entries. */
export function setParams(page: string, params: Record<string, string>) {
  history.replaceState(null, "", href(page, params));
  dispatchEvent(new HashChangeEvent("hashchange"));
}
