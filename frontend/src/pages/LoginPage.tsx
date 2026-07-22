import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";

import GoogleSignInButton from "../components/GoogleSignInButton";
import {
  ApiError,
  getCurrentUser,
  googleLogin,
  login,
  register,
  saveAccessToken,
} from "../services/api-client";

type AuthMode = "login" | "register";

const inputClassName =
  "w-full rounded-xl border border-neutral-300 px-4 py-3 text-neutral-900 outline-none transition focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/15";

export default function LoginPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<AuthMode>("login");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [googleSubmitting, setGoogleSubmitting] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    getCurrentUser()
      .then(() => {
        navigate("/", { replace: true });
      })
      .catch(() => {
        // Không còn phiên hợp lệ nên hiển thị form đăng nhập.
      })
      .finally(() => {
        setCheckingSession(false);
      });
  }, [navigate]);

  function switchMode(nextMode: AuthMode) {
    setMode(nextMode);
    setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (mode === "register" && password.length < 8) {
      setError("Mật khẩu cần có ít nhất 8 ký tự.");
      return;
    }

    setSubmitting(true);
    try {
      const response =
        mode === "login"
          ? await login(email, password)
          : await register(email, password, fullName);
      saveAccessToken(response.access_token);
      navigate("/", { replace: true });
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "Đã có lỗi xảy ra. Vui lòng thử lại.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function submitGoogleCredential(credential: string) {
    setError("");
    setGoogleSubmitting(true);

    try {
      const response = await googleLogin(credential);
      saveAccessToken(response.access_token);
      navigate("/", { replace: true });
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "Đăng nhập Google không thành công. Vui lòng thử lại.",
      );
    } finally {
      setGoogleSubmitting(false);
    }
  }

  if (checkingSession) {
    return (
      <main className="grid min-h-dvh place-items-center bg-white">
        <p className="text-sm text-neutral-500">
          Đang kiểm tra phiên đăng nhập...
        </p>
      </main>
    );
  }

  return (
    <main className="grid min-h-dvh bg-white lg:grid-cols-2">
      <section
        className="hidden items-center justify-center bg-sky-50 p-6 lg:flex"
        aria-hidden="true"
      >
        <img
          src="/brand/background.png"
          alt=""
          className="h-full w-full object-contain"
        />
      </section>

      <section className="flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <Link to="/" aria-label="Về trang trò chuyện">
            <img
              src="/brand/logo.png"
              alt="DocAlly"
              className="mx-auto mb-8 h-20 w-72 object-cover object-center"
            />
          </Link>

          <div className="mb-7 grid grid-cols-2 rounded-xl bg-neutral-100 p-1">
            {(["login", "register"] as const).map((item) => (
              <button
                key={item}
                type="button"
                className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${
                  mode === item
                    ? "bg-white text-neutral-900 shadow-sm"
                    : "text-neutral-500 hover:text-neutral-800"
                }`}
                onClick={() => switchMode(item)}
              >
                {item === "login" ? "Đăng nhập" : "Tạo tài khoản"}
              </button>
            ))}
          </div>

          <h1 className="text-2xl font-bold text-neutral-900">
            {mode === "login"
              ? "Chào mừng bạn quay lại"
              : "Bắt đầu với DocAlly"}
          </h1>
          <p className="mt-2 text-sm leading-6 text-neutral-500">
            {mode === "login"
              ? "Đăng nhập để tiếp tục đọc hiểu tài liệu và xem lại lịch sử."
              : "Tạo tài khoản để lưu tài liệu và các cuộc trò chuyện của bạn."}
          </p>

          <div className="mt-7">
            <GoogleSignInButton
              disabled={submitting || googleSubmitting}
              onCredential={submitGoogleCredential}
              onError={setError}
            />
            {googleSubmitting && (
              <p className="mt-2 text-center text-xs text-neutral-500">
                Đang đăng nhập với Google...
              </p>
            )}
          </div>

          <div className="my-6 flex items-center gap-3" aria-hidden="true">
            <span className="h-px flex-1 bg-neutral-200" />
            <span className="text-xs font-medium text-neutral-400">hoặc</span>
            <span className="h-px flex-1 bg-neutral-200" />
          </div>

          <form className="space-y-4" onSubmit={submit}>
            {mode === "register" && (
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium">
                  Họ và tên
                </span>
                <input
                  type="text"
                  name="fullName"
                  autoComplete="name"
                  maxLength={120}
                  className={inputClassName}
                  placeholder="Nguyễn Văn An"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                />
              </label>
            )}

            <label className="block">
              <span className="mb-1.5 block text-sm font-medium">Email</span>
              <input
                type="email"
                name="email"
                autoComplete="email"
                required
                className={inputClassName}
                placeholder="you@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>

            <label className="block">
              <span className="mb-1.5 block text-sm font-medium">Mật khẩu</span>
              <input
                type="password"
                name="password"
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
                required
                minLength={mode === "register" ? 8 : 1}
                maxLength={128}
                className={inputClassName}
                placeholder="••••••••"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              {mode === "register" && (
                <span className="mt-1.5 block text-xs text-neutral-500">
                  Sử dụng ít nhất 8 ký tự.
                </span>
              )}
            </label>

            {error && (
              <p
                className="rounded-xl bg-red-50 px-3.5 py-3 text-sm text-red-700"
                role="alert"
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={submitting || googleSubmitting}
              className="w-full rounded-xl bg-emerald-600 px-4 py-3 font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-wait disabled:opacity-60"
            >
              {submitting
                ? "Đang xử lý..."
                : mode === "login"
                  ? "Đăng nhập"
                  : "Tạo tài khoản"}
            </button>
          </form>

          <Link
            to="/"
            className="mt-6 block text-center text-sm text-emerald-700 hover:underline"
          >
            Tiếp tục với tư cách khách
          </Link>
        </div>
      </section>
    </main>
  );
}
