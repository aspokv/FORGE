describe("FORGE authenticated fetch", () => {
  beforeEach(() => {
    jest.resetModules();
    localStorage.clear();
  });

  test("anexa o Bearer às chamadas fetch da API, incluindo o Coach", async () => {
    const nativeFetch = jest.fn().mockResolvedValue({ ok: true });
    window.fetch = nativeFetch;
    localStorage.setItem("forge_token", "token-do-atleta");

    await import("./AuthContext");
    const backend = process.env.REACT_APP_BACKEND_URL || "";
    await window.fetch(`${backend}/api/coach`, { method: "POST" });

    const [, options] = nativeFetch.mock.calls[0];
    expect(new Headers(options.headers).get("Authorization")).toBe("Bearer token-do-atleta");
  });

  test("nunca envia o token do atleta para outro domínio", async () => {
    const nativeFetch = jest.fn().mockResolvedValue({ ok: true });
    window.fetch = nativeFetch;
    localStorage.setItem("forge_token", "segredo");

    await import("./AuthContext");
    await window.fetch("https://example.com/asset.json");

    const [, options] = nativeFetch.mock.calls[0];
    expect(options).toEqual({});
  });
});
