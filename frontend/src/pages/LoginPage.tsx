import { Link } from "react-router";

export default function LoginPage() {
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
          <img
            src="/brand/logo.png"
            alt="DocAlly"
            className="mx-auto mb-8 h-20 w-72 object-cover object-center"
          />

          <h1 className="text-2xl font-bold text-neutral-900">
            Đăng nhập vào DocAlly
          </h1>

          <p className="mt-2 text-sm text-neutral-500">
            Tiếp tục đọc hiểu tài liệu và lưu lại lịch sử của bạn.
          </p>

          <form
            className="mt-8 space-y-4"
            onSubmit={(event) => event.preventDefault()}
          >
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium">Email</span>
              <input
                type="email"
                name="email"
                autoComplete="email"
                required
                className="w-full rounded-xl border border-neutral-300 px-4 py-3 outline-none focus:border-blue-500"
                placeholder="you@example.com"
              />
            </label>

            <label className="block">
              <span className="mb-1.5 block text-sm font-medium">Mật khẩu</span>
              <input
                type="password"
                name="password"
                autoComplete="current-password"
                required
                className="w-full rounded-xl border border-neutral-300 px-4 py-3 outline-none focus:border-blue-500"
                placeholder="••••••••"
              />
            </label>

            <button
              type="submit"
              className="w-full rounded-xl bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700"
            >
              Đăng nhập
            </button>
          </form>

          <Link
            to="/"
            className="mt-6 block text-center text-sm text-blue-600 hover:underline"
          >
            Quay lại trang trò chuyện
          </Link>
        </div>
      </section>
    </main>
  );
}
