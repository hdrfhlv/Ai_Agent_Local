import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API = "";
const WELCOME = {
  role: "assistant",
  text: "ET Ini gua udah siap banget bantu lu ngomong bae ya kalo mau bikin invoice atau scraping web ane tunggu gan.",
};
const rupiah = new Intl.NumberFormat("id-ID", {
  style: "currency",
  currency: "IDR",
  maximumFractionDigits: 0,
});

function localDateString(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function monthRange() {
  const today = new Date();
  return {
    start: `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-01`,
    end: localDateString(today),
  };
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(sessionStorage.getItem("kanti_session")
          ? { Authorization: `Bearer ${sessionStorage.getItem("kanti_session")}` }
          : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new Error("Et ini Serper lokalnya ge belom nyambung. Jalanin run-web.bat dulu.");
  }

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.detail || "Gagal permintaan ente gan. Coba lagi.");
    error.status = response.status;
    throw error;
  }
  return body;
}

function BrandMark() {
  return <div className="brand-mark">K</div>;
}

function AuthScreen({
  ownerExists,
  username,
  password,
  confirmation,
  error,
  busy,
  onUsernameChange,
  onPasswordChange,
  onConfirmationChange,
  onSubmit,
}) {
  return (
    <main className="auth-shell">
      <section className="auth-card">
        <div className="auth-brand">
          <BrandMark />
          <div>
            <strong>KANTI</strong>
            <span>LOCAL AI STUDIO</span>
          </div>
        </div>
        <span className="eyebrow">{ownerExists ? "AKUN PEMILIK" : "PENDAFTARAN PERTAMA"}</span>
        <h1>{ownerExists ? "Selamat datang kembali" : "Buat akun pemilik"}</h1>
        <p className="auth-description">
          {ownerExists
            ? "Masuk untuk membuka workspace pribadi Anda."
            : "Buat satu akun pemilik. Pendaftaran akan ditutup setelah akun dibuat."}
        </p>
        <form className="auth-form" onSubmit={onSubmit}>
          <label>
            Nama pengguna
            <input
              autoComplete="username"
              autoFocus
              maxLength={80}
              minLength={3}
              onChange={(event) => onUsernameChange(event.target.value)}
              required
              value={username}
            />
          </label>
          <label>
            Kata sandi
            <input
              autoComplete={ownerExists ? "current-password" : "new-password"}
              maxLength={1024}
              minLength={10}
              onChange={(event) => onPasswordChange(event.target.value)}
              required
              type="password"
              value={password}
            />
          </label>
          {!ownerExists && (
            <label>
              Ulangi kata sandi
              <input
                autoComplete="new-password"
                maxLength={1024}
                minLength={10}
                onChange={(event) => onConfirmationChange(event.target.value)}
                required
                type="password"
                value={confirmation}
              />
            </label>
          )}
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className="primary-button auth-submit" disabled={busy} type="submit">
            {busy ? "Memproses..." : ownerExists ? "Masuk" : "Buat akun pemilik"}
          </button>
        </form>
        <p className="auth-footnote">
          Kata sandi diproses secara lokal dan tidak dikirim ke Groq.
        </p>
      </section>
    </main>
  );
}

function App() {
  const [auth, setAuth] = useState({
    ready: false,
    ownerExists: false,
    authenticated: false,
    username: "",
  });
  const [authUsername, setAuthUsername] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authConfirmation, setAuthConfirmation] = useState("");
  const [authError, setAuthError] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [page, setPage] = useState("chat");
  const [health, setHealth] = useState(null);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([WELCOME]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [vaultStatus, setVaultStatus] = useState({ exists: false, unlocked: false });
  const [vaultEntries, setVaultEntries] = useState([]);
  const [masterPassword, setMasterPassword] = useState("");
  const [masterConfirmation, setMasterConfirmation] = useState("");
  const [vaultLoading, setVaultLoading] = useState(false);
  const [service, setService] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [notes, setNotes] = useState("");
  const [revealed, setRevealed] = useState({});
  const [generatedPassword, setGeneratedPassword] = useState("");
  const [passwordLength, setPasswordLength] = useState(16);
  const initialMonth = monthRange();
  const [financeSummary, setFinanceSummary] = useState(null);
  const [financeStart, setFinanceStart] = useState(initialMonth.start);
  const [financeEnd, setFinanceEnd] = useState(initialMonth.end);
  const [financeLoading, setFinanceLoading] = useState(false);
  const [financeSaving, setFinanceSaving] = useState(false);
  const [transactionKind, setTransactionKind] = useState("pemasukan");
  const [transactionDescription, setTransactionDescription] = useState("");
  const [transactionAmount, setTransactionAmount] = useState("");
  const [transactionDate, setTransactionDate] = useState(localDateString);
  const [transactionCategory, setTransactionCategory] = useState("");
  const bottomRef = useRef(null);

  const refreshHealth = useCallback(async () => {
    try {
      const result = await request("/api/health");
      setHealth(result);
      setVaultStatus({
        exists: result.vault_exists,
        unlocked: result.vault_unlocked,
      });
    } catch (requestError) {
      setError(requestError.message);
    }
  }, []);

  const submitAuth = async (event) => {
    event.preventDefault();
    setAuthError("");
    if (!auth.ownerExists && authPassword !== authConfirmation) {
      setAuthError("Kata sandi dan konfirmasinya belum sama.");
      return;
    }
    setAuthBusy(true);
    try {
      const result = await request(
        auth.ownerExists ? "/api/auth/login" : "/api/auth/register",
        {
          method: "POST",
          body: JSON.stringify({
            username: authUsername,
            password: authPassword,
          }),
        },
      );
      sessionStorage.setItem("kanti_session", result.token);
      setAuth({
        ready: true,
        ownerExists: true,
        authenticated: true,
        username: result.username,
      });
      setAuthPassword("");
      setAuthConfirmation("");
      setAuthError("");
    } catch (requestError) {
      setAuthError(requestError.message);
      if (requestError.status === 409) {
        setAuth((current) => ({ ...current, ownerExists: true }));
      }
    } finally {
      setAuthBusy(false);
    }
  };

  const signOut = async () => {
    try {
      await request("/api/auth/logout", { method: "POST" });
    } catch (requestError) {
      setAuthError(requestError.message);
    } finally {
      sessionStorage.removeItem("kanti_session");
      setAuth((current) => ({
        ...current,
        authenticated: false,
        ownerExists: true,
      }));
      setHealth(null);
      setMessages([WELCOME]);
      setConversationId(null);
      setPage("chat");
    }
  };

  const refreshVaultEntries = useCallback(async () => {
    const result = await request("/api/vault/entries");
    setVaultEntries(result.item);
  }, []);

  const refreshFinance = useCallback(async () => {
    setFinanceLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({
        tanggal_mulai: financeStart,
        tanggal_akhir: financeEnd,
      });
      setFinanceSummary(await request(`/api/finance/summary?${query}`));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setFinanceLoading(false);
    }
  }, [financeEnd, financeStart]);

  useEffect(() => {
    let active = true;
    const restoreSession = async () => {
      try {
        const status = await request("/api/auth/status");
        let username = "";
        let authenticated = false;
        const token = sessionStorage.getItem("kanti_session");
        if (token) {
          try {
            const session = await request("/api/auth/session");
            username = session.username;
            authenticated = true;
          } catch {
            sessionStorage.removeItem("kanti_session");
          }
        }
        if (active) {
          setAuth({
            ready: true,
            ownerExists: status.owner_exists,
            authenticated,
            username,
          });
        }
      } catch (requestError) {
        if (active) {
          setAuthError(requestError.message);
          setAuth((current) => ({ ...current, ready: true }));
        }
      }
    };
    restoreSession();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (auth.authenticated) refreshHealth();
  }, [auth.authenticated, refreshHealth]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  useEffect(() => {
    if (auth.authenticated && page === "vault" && vaultStatus.unlocked) {
      refreshVaultEntries().catch((requestError) => setError(requestError.message));
    }
  }, [auth.authenticated, page, vaultStatus.unlocked, refreshVaultEntries]);

  useEffect(() => {
    if (auth.authenticated && page === "finance") refreshFinance();
  }, [auth.authenticated, page, refreshFinance]);

  const startNewChat = () => {
    setConversationId(null);
    setMessages([WELCOME]);
    setDraft("");
    setPage("chat");
    setError("");
  };

  const sendMessage = async (text = draft) => {
    const message = text.trim();
    if (!message || sending) return;
    setDraft("");
    setError("");
    setMessages((current) => [...current, { role: "user", text: message }]);
    setSending(true);
    try {
      const result = await request("/api/chat", {
        method: "POST",
        body: JSON.stringify({
          message,
          conversation_id: conversationId,
        }),
      });
      setConversationId(result.conversation_id);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          text: result.reply,
          artifacts: result.artifacts || [],
        },
      ]);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSending(false);
    }
  };

  const saveTransaction = async (event) => {
    event.preventDefault();
    setFinanceSaving(true);
    setError("");
    try {
      await request("/api/finance/transactions", {
        method: "POST",
        body: JSON.stringify({
          jenis: transactionKind,
          keterangan: transactionDescription,
          jumlah: Number(transactionAmount),
          tanggal: transactionDate,
          kategori: transactionCategory,
        }),
      });
      setTransactionDescription("");
      setTransactionAmount("");
      setTransactionCategory("");
      await refreshFinance();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setFinanceSaving(false);
    }
  };

  const removeTransaction = async (transaction) => {
    if (!window.confirm(`Hapus catatan "${transaction.keterangan}"?`)) return;
    setError("");
    try {
      await request(`/api/finance/transactions/${transaction.id}`, {
        method: "DELETE",
      });
      await refreshFinance();
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const openVault = async (event) => {
    event.preventDefault();
    setVaultLoading(true);
    setError("");
    try {
      await request("/api/vault/open", {
        method: "POST",
        body: JSON.stringify({
          master_password: masterPassword,
          ...(vaultStatus.exists ? {} : { confirmation: masterConfirmation }),
        }),
      });
      setMasterPassword("");
      setMasterConfirmation("");
      setVaultStatus((current) => ({ ...current, unlocked: true, exists: true }));
      await refreshVaultEntries();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setVaultLoading(false);
    }
  };

  const lockVault = async () => {
    setVaultLoading(true);
    setError("");
    try {
      await request("/api/vault/lock", { method: "POST" });
      setVaultStatus((current) => ({ ...current, unlocked: false }));
      setVaultEntries([]);
      setRevealed({});
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setVaultLoading(false);
    }
  };

  const saveVaultEntry = async (event) => {
    event.preventDefault();
    setVaultLoading(true);
    setError("");
    try {
      const payload = { layanan: service, username, password, catatan: notes };
      try {
        await request("/api/vault/entries", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      } catch (requestError) {
        if (requestError.status !== 409 || !window.confirm(`${requestError.message}\n\nTimpa password yang tersimpan?`)) {
          throw requestError;
        }
        await request("/api/vault/entries", {
          method: "POST",
          body: JSON.stringify({ ...payload, timpa: true }),
        });
      }
      setService("");
      setUsername("");
      setPassword("");
      setNotes("");
      await refreshVaultEntries();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setVaultLoading(false);
    }
  };

  const revealPassword = async (layanan) => {
    setError("");
    if (revealed[layanan]) {
      setRevealed((current) => ({ ...current, [layanan]: null }));
      return;
    }
    try {
      const result = await request(`/api/vault/entries/${encodeURIComponent(layanan)}`);
      setRevealed((current) => ({ ...current, [layanan]: result.password }));
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const deleteVaultEntry = async (layanan) => {
    if (!window.confirm(`Hapus password untuk ${layanan}?`)) return;
    try {
      await request(`/api/vault/entries/${encodeURIComponent(layanan)}`, {
        method: "DELETE",
      });
      await refreshVaultEntries();
      setRevealed((current) => {
        const next = { ...current };
        delete next[layanan];
        return next;
      });
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const generatePassword = async () => {
    setError("");
    try {
      const result = await request("/api/vault/generate", {
        method: "POST",
        body: JSON.stringify({ panjang: Number(passwordLength) }),
      });
      setGeneratedPassword(result.password);
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const copyText = async (value) => {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      setError("Mantog Clipboardnya ga tersedia di web enih.");
    }
  };

  if (!auth.ready) {
    return (
      <main className="auth-shell">
        <div className="auth-card loading-card">Memeriksa akses...</div>
      </main>
    );
  }

  if (!auth.authenticated) {
    return (
      <AuthScreen
        ownerExists={auth.ownerExists}
        username={authUsername}
        password={authPassword}
        confirmation={authConfirmation}
        error={authError}
        busy={authBusy}
        onUsernameChange={setAuthUsername}
        onPasswordChange={setAuthPassword}
        onConfirmationChange={setAuthConfirmation}
        onSubmit={submitAuth}
      />
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" onClick={(event) => event.preventDefault()}>
          <BrandMark />
          <span className="brand-copy">
            <strong>KANTI</strong>
            <small>LOCAL AI STUDIO</small>
          </span>
        </a>

        <button className="new-chat-button" onClick={startNewChat}>
          <span>＋</span> Percakapan baru
        </button>

        <div className="nav-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Navigasi utama">
          <button
            className={page === "chat" ? "nav-item active" : "nav-item"}
            onClick={() => setPage("chat")}
          >
            <span className="nav-icon">◉</span> Asisten AI
          </button>
          <button
            className={page === "finance" ? "nav-item active" : "nav-item"}
            onClick={() => {
              setPage("finance");
              setError("");
            }}
          >
            <span className="nav-icon">$</span> Keuangan
          </button>
          <button
            className={page === "vault" ? "nav-item active" : "nav-item"}
            onClick={() => {
              setPage("vault");
              setError("");
              refreshHealth();
            }}
          >
            <span className="nav-icon">⌑</span> Password vault
            <span className={vaultStatus.unlocked ? "nav-status online" : "nav-status"} />
          </button>
        </nav>

        <div className="sidebar-note">
          <div className="note-icon">✦</div>
          <strong>Lokalan dulu</strong>
          <p>Enih File nya di buat di komputernya si iday. Pesa chatnya di proses ama abang Groq.</p>
        </div>

        <div className="profile">
          <div className="avatar">K</div>
          <div className="profile-copy">
            <strong>Karya Anugerah Tijarah</strong>
            <small>Partner Digital Anda</small>
          </div>
          <span className="profile-menu">···</span>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <span className="crumb-separator">/</span>
            <strong>
              {page === "chat"
                ? "Asisten AI"
                : page === "vault"
                  ? "Password vault"
                  : page === "finance"
                    ? "Keuangan"
                    : "Keuangan"}
            </strong>
          </div>
          <div className="topbar-right">
            <span className={health?.assistant_ready ? "server-pill" : "server-pill disconnected"}>
              <i /> {health ? (health.assistant_ready ? "Server lokal aktif" : "API key perlu diatur") : "Menghubungkan"}
            </span>
            <button className="logout-button" onClick={signOut}>Keluar</button>
            <div className="topbar-avatar">K</div>
          </div>
        </header>

        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button onClick={() => setError("")} aria-label="Tutup pesan error">
              ×
            </button>
          </div>
        )}

        {page === "chat" && (
          <section className="chat-page">
            <div className="chat-heading">
              <span className="eyebrow">KANTI AI · PARTNER DIGITAL ANDA</span>
              <h1>Ide hebat dimulai dari sinih orang betawi.</h1>
              <p>Asisten betawi siap ngebantu.</p>
            </div>

            <div className="conversation">
              {messages.map((message, index) => (
                <div
                  className={`message-row ${message.role}`}
                  key={`${message.role}-${index}`}
                >
                  {message.role === "assistant" && (
                    <div className="message-avatar">
                      <BrandMark />
                    </div>
                  )}
                  <div className="message-content">
                    {message.role === "assistant" && (
                      <div className="message-author">KANTI AI</div>
                    )}
                    {message.role === "assistant" ? (
                      <div className="message-bubble markdown-content">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            table: ({ children }) => (
                              <div className="markdown-table-wrap">
                                <table>{children}</table>
                              </div>
                            ),
                          }}
                        >
                          {message.text}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <div className="message-bubble">{message.text}</div>
                    )}
                    {message.artifacts?.length > 0 && (
                      <div className="artifact-list">
                        {message.artifacts.map((artifact) => (
                          <a
                            className="artifact-link"
                            href={artifact.url}
                            key={artifact.url}
                          >
                            <span>↧</span> Unduh {artifact.name}
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {sending && (
                <div className="message-row assistant">
                  <div className="message-avatar">
                    <BrandMark />
                  </div>
                  <div className="message-content">
                    <div className="message-author">KANTI AI</div>
                    <div className="message-bubble typing">
                      <i /><i /><i /><span>Sabar lagi nyiapian jawaban...</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {messages.length === 1 && (
              <div className="suggestions">
                <button
                  onClick={() =>
                    sendMessage(
                      "Buat invoice untuk PT Maju Jaya: Pembuatan website, harga Rp2.500.000",
                    )
                  }
                >
                  <span className="suggestion-icon blue">▤</span>
                  <span><strong>Buat invoice</strong><small>Susun invoice PDF dari chat</small></span>
                  <b>↗</b>
                </button>
                <button
                  onClick={() =>
                    setDraft("Bantu saya scrape katalog produk dari https://books.toscrape.com/")
                  }
                >
                  <span className="suggestion-icon teal">⌕</span>
                  <span><strong>Ambil data produk</strong><small>Scrape katalog ke Excel</small></span>
                  <b>↗</b>
                </button>
                <button onClick={() => setPage("vault")}>
                  <span className="suggestion-icon violet">⌑</span>
                  <span><strong>Kelola password</strong><small>Vault terenkripsi di perangkatmu</small></span>
                  <b>↗</b>
                </button>
              </div>
            )}

            <form
              className="composer"
              onSubmit={(event) => {
                event.preventDefault();
                sendMessage();
              }}
            >
              <textarea
                aria-label="Pesan untuk KANTI AI"
                placeholder="Tulis pesan untuk KANTI AI..."
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    sendMessage();
                  }
                }}
                rows={2}
                maxLength={4000}
              />
              <div className="composer-footer">
                <span className="composer-hint">
                  <span>↵</span> Enter untuk kirim · Shift + Enter untuk baris baru
                </span>
                <button
                  className="send-button"
                  type="submit"
                  disabled={!draft.trim() || sending}
                  aria-label="Kirim pesan"
                >
                  {sending ? "…" : "↑"}
                </button>
              </div>
            </form>
            <p className="privacy-hint">
              <span>♧</span> Jangan kirim password atau master password melalui chat, ntar gua colong, AWASS.
            </p>
          </section>
        )}

        {page === "vault" && (
          <section className="content-page">
            <div className="page-title-row">
              <div>
                <span className="eyebrow">AMAN DI PERANGKAT INI</span>
                <h1>Password vault</h1>
                <p>Password dienkripsi lokal dan tidak pernah dikirim ke AI.</p>
              </div>
              {vaultStatus.unlocked && (
                <button className="secondary-button" onClick={lockVault} disabled={vaultLoading}>
                  Kunci vault
                </button>
              )}
            </div>

            {!vaultStatus.unlocked ? (
              <form className="surface-card unlock-card" onSubmit={openVault}>
                <div className="card-symbol">⌑</div>
                <h2>{vaultStatus.exists ? "Buka brankas kamu" : "Buat brankas baru"}</h2>
                <p>
                  {vaultStatus.exists
                    ? "Masukkan master password untuk membuka vault."
                    : "Pilih master password minimal 8 karakter dan simpan baik-baik."}
                </p>
                <label>
                  Master password
                  <input
                    type="password"
                    value={masterPassword}
                    onChange={(event) => setMasterPassword(event.target.value)}
                    autoComplete="current-password"
                    required
                  />
                </label>
                {!vaultStatus.exists && (
                  <label>
                    Ulangi master password
                    <input
                      type="password"
                      value={masterConfirmation}
                      onChange={(event) => setMasterConfirmation(event.target.value)}
                      autoComplete="new-password"
                      minLength={8}
                      required
                    />
                  </label>
                )}
                <button className="primary-button full-width" disabled={vaultLoading}>
                  {vaultLoading ? "Memproses..." : vaultStatus.exists ? "Buka vault" : "Buat vault"}
                </button>
              </form>
            ) : (
              <div className="vault-layout">
                <form className="surface-card save-card" onSubmit={saveVaultEntry}>
                  <div className="card-heading">
                    <div><h2>Simpan layanan</h2><p>Tambahkan akun ke vault terenkripsi.</p></div>
                    <span className="card-icon">＋</span>
                  </div>
                  <label>Nama layanan<input value={service} onChange={(event) => setService(event.target.value)} placeholder="Contoh: Email kerja" required /></label>
                  <label>Username atau email<input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="nama@email.com" /></label>
                  <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" required /></label>
                  <label>Catatan <span className="optional">(opsional)</span><textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={2} /></label>
                  <button className="primary-button full-width" disabled={vaultLoading}>Simpan ke vault</button>
                </form>

                <div className="vault-right">
                  <section className="surface-card entries-card">
                    <div className="card-heading">
                      <div><h2>Layanan tersimpan</h2><p>{vaultEntries.length} akun di dalam vault</p></div>
                      <span className="secure-badge"><i /> Terenkripsi</span>
                    </div>
                    {vaultEntries.length === 0 ? (
                      <div className="empty-state">
                        <span>◌</span><strong>Vault masih kosong</strong>
                        <p>Layanan yang kamu simpan akan muncul di sini.</p>
                      </div>
                    ) : (
                      <div className="entry-list">
                        {vaultEntries.map((entry) => (
                          <div className="entry-row" key={entry.layanan}>
                            <div className="service-icon">{entry.layanan.slice(0, 1).toUpperCase()}</div>
                            <div className="entry-main">
                              <strong>{entry.layanan}</strong>
                              <small>{entry.username || "Tanpa username"}</small>
                              {revealed[entry.layanan] && <code>{revealed[entry.layanan]}</code>}
                            </div>
                            <button className="icon-button" onClick={() => revealPassword(entry.layanan)} title="Tampilkan atau sembunyikan password">
                              {revealed[entry.layanan] ? "◉" : "◎"}
                            </button>
                            <button className="icon-button danger" onClick={() => deleteVaultEntry(entry.layanan)} title="Hapus layanan">×</button>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>

                  <section className="surface-card generator-card">
                    <div className="card-heading">
                      <div><h2>Generator password</h2><p>Buat password kuat secara lokal.</p></div>
                      <span className="card-icon">✳</span>
                    </div>
                    <div className="generator-controls">
                      <label>Panjang<input type="number" min="8" max="128" value={passwordLength} onChange={(event) => setPasswordLength(event.target.value)} /></label>
                      <button className="primary-button" onClick={generatePassword}>Buat password</button>
                    </div>
                    {generatedPassword && (
                      <div className="generated-output">
                        <code>{generatedPassword}</code>
                        <button className="icon-button" onClick={() => copyText(generatedPassword)} title="Salin password">▢</button>
                      </div>
                    )}
                  </section>
                </div>
              </div>
            )}
          </section>
        )}

        {page === "finance" && (
          <section className="content-page finance-page">
            <div className="page-title-row">
              <div>
                <span className="eyebrow">PEMBUKUAN LOKAL</span>
                <h1>Keuangan</h1>
                <p>Catat arus kas dan pantau laba-rugi dari transaksi yang tersimpan.</p>
              </div>
              <button className="secondary-button" onClick={refreshFinance} disabled={financeLoading}>
                {financeLoading ? "Memuat..." : "Segarkan"}
              </button>
            </div>

            <div className="finance-period surface-card">
              <div>
                <strong>Periode laporan</strong>
                <small>Saldo kas menunjukkan pemasukan dikurangi pengeluaran yang tercatat hingga tanggal akhir.</small>
              </div>
              <label>Dari<input type="date" value={financeStart} max={financeEnd} onChange={(event) => setFinanceStart(event.target.value)} /></label>
              <label>Sampai<input type="date" value={financeEnd} min={financeStart} onChange={(event) => setFinanceEnd(event.target.value)} /></label>
            </div>

            {financeLoading && !financeSummary ? (
              <div className="surface-card loading-card">Memuat laporan keuangan...</div>
            ) : financeSummary ? (
              <>
                <div className="finance-metrics">
                  <FinanceMetric label="Saldo kas bersih" value={financeSummary.saldo_kas} icon="◉" tone="blue" helper="Akumulasi sampai tanggal akhir" />
                  <FinanceMetric label="Total pemasukan" value={financeSummary.pemasukan} icon="↗" tone="green" helper="Sesuai periode laporan" />
                  <FinanceMetric label="Total pengeluaran" value={financeSummary.pengeluaran} icon="↙" tone="orange" helper="Sesuai periode laporan" />
                  <FinanceMetric label="Laba / rugi" value={financeSummary.laba_rugi} icon="∑" tone={financeSummary.laba_rugi >= 0 ? "green" : "red"} helper={`${financeSummary.jumlah_transaksi} transaksi dalam periode`} />
                </div>

                <section className="surface-card expense-analysis" aria-labelledby="expense-analysis-title">
                  <div className="card-heading">
                    <div>
                      <h2 id="expense-analysis-title">Pengeluaran per kategori</h2>
                      <p>Perbandingan pengeluaran selama periode laporan.</p>
                    </div>
                    <span className="card-icon">↙</span>
                  </div>
                  {!Array.isArray(financeSummary.pengeluaran_per_kategori) ? (
                    <p className="finance-analysis-warning" role="status">
                      Backend belum memuat analisis kategori. Hentikan server lama lalu jalankan kembali run-web.bat.
                    </p>
                  ) : financeSummary.pengeluaran_per_kategori.length === 0 ? (
                    <div className="empty-state">
                      <span>◌</span><strong>Belum ada pengeluaran</strong>
                      <p>Pengeluaran akan dikelompokkan di sini setelah dicatat.</p>
                    </div>
                  ) : (
                    <div className="expense-category-list">
                      {financeSummary.pengeluaran_per_kategori.map((item) => {
                        const largestExpense = financeSummary.pengeluaran_per_kategori[0].jumlah;
                        const barWidth = Math.max(4, (item.jumlah / largestExpense) * 100);
                        const share = Math.round((item.jumlah / financeSummary.pengeluaran) * 100);
                        return (
                          <div className="expense-category" key={item.kategori}>
                            <div className="expense-category-heading">
                              <strong>{item.kategori}</strong>
                              <span>{rupiah.format(item.jumlah)} <small>{share}%</small></span>
                            </div>
                            <div
                              className="expense-category-track"
                              role="img"
                              aria-label={`${item.kategori}: ${rupiah.format(item.jumlah)}, ${share}% dari total pengeluaran`}
                            >
                              <div className="expense-category-bar" style={{ width: `${barWidth}%` }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </section>

                <div className="finance-layout">
                  <form className="surface-card finance-form" onSubmit={saveTransaction}>
                    <div className="card-heading">
                      <div><h2>Catat transaksi</h2><p>Catatan tersimpan lokal di perangkat ini.</p></div>
                      <span className="card-icon">＋</span>
                    </div>
                    <div className="finance-type-switch" role="group" aria-label="Jenis transaksi">
                      <button type="button" className={transactionKind === "pemasukan" ? "selected income" : ""} onClick={() => setTransactionKind("pemasukan")}>↗ Pemasukan</button>
                      <button type="button" className={transactionKind === "pengeluaran" ? "selected expense" : ""} onClick={() => setTransactionKind("pengeluaran")}>↙ Pengeluaran</button>
                    </div>
                    <label>Keterangan<input value={transactionDescription} onChange={(event) => setTransactionDescription(event.target.value)} maxLength={500} placeholder="Contoh: Pembayaran proyek website" required /></label>
                    <label>Jumlah (Rupiah)<input type="number" min="1" step="1" value={transactionAmount} onChange={(event) => setTransactionAmount(event.target.value)} placeholder="2500000" required /></label>
                    <div className="finance-form-row">
                      <label>Tanggal<input type="date" value={transactionDate} onChange={(event) => setTransactionDate(event.target.value)} required /></label>
                      <label>Kategori <span className="optional">(opsional)</span><input value={transactionCategory} onChange={(event) => setTransactionCategory(event.target.value)} maxLength={100} placeholder="Proyek" /></label>
                    </div>
                    <button className="primary-button full-width" disabled={financeSaving}>{financeSaving ? "Menyimpan..." : "Simpan transaksi"}</button>
                    <p className="finance-form-note">AI juga bisa mencatat, misalnya: “Catat pemasukan jasa website Rp2.500.000 hari ini.”</p>
                  </form>

                  <section className="surface-card finance-transactions">
                    <div className="card-heading">
                      <div><h2>Transaksi</h2><p>{financeSummary.tanggal_mulai} — {financeSummary.tanggal_akhir}</p></div>
                      <span className="transaction-count">{financeSummary.jumlah_transaksi}</span>
                    </div>
                    {financeSummary.transaksi.length === 0 ? (
                      <div className="empty-state">
                        <span>◌</span><strong>Belum ada transaksi</strong>
                        <p>Tambahkan pemasukan atau pengeluaran untuk mulai melihat laporan.</p>
                      </div>
                    ) : (
                      <div className="finance-transaction-list">
                        {financeSummary.transaksi.map((transaction) => (
                          <div className="finance-transaction" key={transaction.id}>
                            <div className={`transaction-icon ${transaction.jenis}`}>
                              {transaction.jenis === "pemasukan" ? "↗" : "↙"}
                            </div>
                            <div className="transaction-details">
                              <strong>{transaction.keterangan}</strong>
                              <small>{transaction.tanggal}{transaction.kategori ? ` · ${transaction.kategori}` : ""}</small>
                            </div>
                            <strong className={`transaction-amount ${transaction.jenis}`}>
                              {transaction.jenis === "pemasukan" ? "+" : "−"}{rupiah.format(transaction.jumlah)}
                            </strong>
                            <button className="icon-button danger" onClick={() => removeTransaction(transaction)} title="Hapus transaksi" aria-label={`Hapus ${transaction.keterangan}`}>×</button>
                          </div>
                        ))}
                        {financeSummary.transaksi_dibatasi && (
                          <p className="finance-form-note">Daftar menampilkan maksimal 500 transaksi; total laporan tetap menghitung semuanya.</p>
                        )}
                      </div>
                    )}
                  </section>
                </div>
              </>
            ) : null}
            <p className="finance-disclaimer">Ringkasan ini adalah pembukuan kas sederhana dari transaksi yang dicatat, bukan neraca formal atau laporan pajak.</p>
          </section>
        )}

        <footer className="main-footer">
          <span>KANTI · Karya Anugerah Tijarah</span>
          <span>Partner Digital Anda</span>
        </footer>
      </main>
    </div>
  );
}

function FinanceMetric({ label, value, icon, tone, helper }) {
  return (
    <article className="surface-card finance-metric">
      <div className="metric-topline">
        <span>{label}</span>
        <span className={`metric-icon ${tone}`}>{icon}</span>
      </div>
      <strong className={tone === "red" ? "negative-value" : ""}>{rupiah.format(value)}</strong>
      <small>{helper}</small>
    </article>
  );
}

export default App;
