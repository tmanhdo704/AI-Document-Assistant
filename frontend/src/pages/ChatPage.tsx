import { FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router";

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
};

const sampleChats = [
  { title: "Tóm tắt báo cáo quý IV", group: "Hôm nay" },
  { title: "Phân tích hợp đồng thuê nhà", group: "Hôm nay" },
  { title: "Các ý chính trong giáo trình", group: "7 ngày trước" },
  { title: "So sánh hai chính sách", group: "7 ngày trước" },
];

const suggestions = [
  {
    title: "Tóm tắt tài liệu",
    description: "Rút ra những ý chính quan trọng nhất",
  },
  {
    title: "Giải thích nội dung",
    description: "Diễn giải một khái niệm theo cách dễ hiểu",
  },
  {
    title: "Tìm thông tin",
    description: "Tra cứu chi tiết và dẫn nguồn theo trang",
  },
  {
    title: "Tạo câu hỏi ôn tập",
    description: "Biến tài liệu thành bộ câu hỏi ngắn",
  },
];

const focusRing =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-neutral-900";

function getInitialTheme(): boolean {
  const savedTheme = localStorage.getItem("docalley-theme");
  if (savedTheme) return savedTheme === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export default function ChatPage() {
  const [darkMode, setDarkMode] = useState(getInitialTheme);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = darkMode ? "dark" : "light";
    localStorage.setItem("docalley-theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  function startNewChat() {
    setMessages([]);
    setInput("");
    setSidebarOpen(false);
  }

  function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = input.trim();
    if (!content) return;

    setMessages((current) => [
      ...current,
      { id: Date.now(), role: "user", content },
      {
        id: Date.now() + 1,
        role: "assistant",
        content:
          "Đây là bản xem trước giao diện. Câu hỏi sẽ được trả lời khi chúng ta kết nối backend và hệ thống RAG.",
      },
    ]);
    setInput("");
  }

  return (
    <div className="flex h-dvh overflow-hidden bg-white font-sans text-neutral-900 transition-colors dark:bg-[#212121] dark:text-neutral-100">
      <button
        className={`fixed top-3 left-3 z-20 grid size-9 place-items-center rounded-lg bg-transparent text-base hover:bg-neutral-100 md:hidden dark:hover:bg-neutral-800 ${focusRing}`}
        type="button"
        aria-label="Mở thanh bên"
        onClick={() => setSidebarOpen(true)}
      >
        ☰
      </button>

      {sidebarOpen && (
        <button
          className="fixed inset-0 z-20 bg-black/45 md:hidden"
          type="button"
          aria-label="Đóng thanh bên"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-[min(300px,88vw)] shrink-0 flex-col border-r border-neutral-200/70 bg-[#f7f7f8] p-3 shadow-2xl transition-transform duration-200 md:static md:w-[272px] md:translate-x-0 md:shadow-none dark:border-neutral-800 dark:bg-[#171717] ${
          sidebarOpen ? "translate-x-0" : "-translate-x-[105%]"
        }`}
      >
        <div className="flex min-h-10 items-center justify-between px-1">
          <Link
            to="/"
            aria-label="DocAlly - Trang chủ"
            className={`inline-flex items-center rounded-lg ${focusRing}`}
          >
            <img
              src="/brand/logo.png"
              alt="DocAlly"
              className="h-10 w-36 rounded-md bg-white object-cover object-center"
            />
          </Link>
          <button
            className={`grid size-9 place-items-center rounded-lg bg-transparent text-2xl text-neutral-500 hover:bg-neutral-200 md:hidden dark:text-neutral-400 dark:hover:bg-neutral-800 ${focusRing}`}
            type="button"
            aria-label="Đóng thanh bên"
            onClick={() => setSidebarOpen(false)}
          >
            ×
          </button>
        </div>

        <button
          className={`mt-3 flex w-full items-center gap-2.5 rounded-[10px] border border-neutral-200 bg-white px-3 py-2.5 text-left text-sm font-semibold transition hover:border-neutral-300 hover:bg-neutral-100 active:scale-[0.985] dark:border-neutral-700 dark:bg-neutral-800 dark:hover:border-neutral-600 dark:hover:bg-neutral-700 ${focusRing}`}
          type="button"
          onClick={startNewChat}
        >
          <span className="text-xl leading-none font-light" aria-hidden="true">
            ＋
          </span>
          Cuộc trò chuyện mới
        </button>

        <nav
          className="mt-5 min-h-0 flex-1 overflow-y-auto [scrollbar-width:thin]"
          aria-label="Lịch sử trò chuyện"
        >
          {["Hôm nay", "7 ngày trước"].map((group) => (
            <div className="mb-5 last:mb-0" key={group}>
              <p className="mx-2.5 mb-1.5 text-xs font-semibold text-neutral-500 dark:text-neutral-400">
                {group}
              </p>
              {sampleChats
                .filter((chat) => chat.group === group)
                .map((chat, index) => {
                  const active = group === "Hôm nay" && index === 0;
                  return (
                    <button
                      className={`flex w-full items-center gap-2.5 overflow-hidden rounded-lg px-2.5 py-2 text-left text-[0.84rem] transition hover:bg-neutral-200 dark:hover:bg-neutral-800 ${
                        active
                          ? "bg-neutral-200 dark:bg-neutral-800"
                          : "bg-transparent"
                      } ${focusRing}`}
                      type="button"
                      key={chat.title}
                    >
                      <span
                        className="text-lg text-neutral-500"
                        aria-hidden="true"
                      >
                        ◌
                      </span>
                      <span className="truncate">{chat.title}</span>
                    </button>
                  );
                })}
            </div>
          ))}
        </nav>

        <div className="border-t border-neutral-200 pt-2.5 dark:border-neutral-800">
          <div className="flex w-full items-center gap-2.5 rounded-[10px] px-2 py-2.5">
            <span
              className="grid size-8 place-items-center text-base text-neutral-500 dark:text-neutral-400"
              aria-hidden="true"
            >
              {darkMode ? "☾" : "☀"}
            </span>
            <span className="flex min-w-0 flex-1 flex-col text-left">
              <strong className="text-[0.81rem] font-semibold">
                Giao diện tối
              </strong>
              <small className="mt-0.5 truncate text-[0.68rem] text-neutral-500 dark:text-neutral-400">
                Dễ nhìn hơn vào ban đêm
              </small>
            </span>
            <button
              className={`relative h-[21px] w-9 shrink-0 rounded-full transition-colors ${
                darkMode ? "bg-emerald-500" : "bg-neutral-300"
              } ${focusRing}`}
              type="button"
              role="switch"
              aria-checked={darkMode}
              aria-label="Bật hoặc tắt giao diện tối"
              onClick={() => setDarkMode((current) => !current)}
            >
              <span
                className={`absolute top-[3px] left-[3px] size-[15px] rounded-full bg-white shadow-sm transition-transform ${
                  darkMode ? "translate-x-[15px]" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          <button
            className={`mt-1 flex w-full items-center gap-2.5 rounded-[10px] bg-transparent px-2 py-2 text-left hover:bg-neutral-200 dark:hover:bg-neutral-800 ${focusRing}`}
            type="button"
          >
            <span className="grid size-8 place-items-center rounded-full bg-violet-500 text-xs font-bold text-white">
              K
            </span>
            <span className="flex min-w-0 flex-1 flex-col">
              <strong className="text-[0.81rem] font-semibold">Khách</strong>
              <small className="mt-0.5 truncate text-[0.68rem] text-neutral-500 dark:text-neutral-400">
                Đăng nhập để lưu lịch sử
              </small>
            </span>
            <span className="text-neutral-500" aria-hidden="true">
              ···
            </span>
          </button>
        </div>
      </aside>

      <main className="relative flex h-full min-w-0 flex-1 flex-col bg-white dark:bg-[#212121]">
        <header className="flex h-[58px] items-center justify-between py-2 pr-3 pl-[54px] md:px-[18px]">
          <button
            className={`rounded-lg bg-transparent px-2.5 py-2 text-base font-semibold hover:bg-neutral-100 dark:hover:bg-neutral-800 ${focusRing}`}
            type="button"
          >
            DocAlly <span className="ml-1 text-neutral-500">⌄</span>
          </button>
          <Link
            to="/login"
            className={`rounded-full bg-neutral-900 px-4 py-2 text-[0.82rem] font-semibold text-white transition hover:opacity-80 dark:bg-white dark:text-neutral-900 ${focusRing}`}
          >
            Đăng nhập
          </Link>
        </header>

        <section
          className={`flex min-h-0 flex-1 overflow-y-auto ${
            messages.length ? "justify-start" : "justify-center"
          }`}
        >
          {messages.length === 0 ? (
            <div className="mt-0 w-[min(760px,calc(100%-28px))] self-center text-center md:-mt-8 md:w-[min(760px,calc(100%-40px))]">
              <div className="mx-auto mb-5 grid size-12 place-items-center rounded-[15px] bg-emerald-600 text-lg font-extrabold text-white shadow-[0_6px_18px_rgb(16_163_127_/_22%)] dark:bg-emerald-500">
                D
              </div>
              <h1 className="m-0 text-[clamp(1.75rem,4vw,2.25rem)] font-semibold tracking-[-0.035em]">
                Xin chào, mình có thể giúp gì?
              </h1>
              <p className="mx-auto mt-3 mb-6 max-w-xl text-[0.95rem] leading-relaxed text-neutral-500 md:mb-8 dark:text-neutral-400">
                Tải tài liệu PDF lên và đặt câu hỏi. Câu trả lời sẽ đi kèm trích
                dẫn để bạn dễ dàng kiểm chứng.
              </p>

              <div className="grid w-full grid-cols-1 gap-2.5 md:grid-cols-2">
                {suggestions.map((suggestion, index) => (
                  <button
                    className={`relative flex min-h-[88px] flex-col rounded-[14px] border border-neutral-200 bg-white py-4 pr-10 pl-4 text-left transition hover:-translate-y-px hover:border-neutral-300 hover:bg-neutral-50 md:min-h-[104px] dark:border-neutral-700 dark:bg-neutral-800 dark:hover:border-neutral-600 dark:hover:bg-neutral-700 ${
                      index > 1 ? "hidden md:flex" : "flex"
                    } ${focusRing}`}
                    type="button"
                    key={suggestion.title}
                    onClick={() => setInput(suggestion.title)}
                  >
                    <span
                      className="absolute top-3.5 right-4 text-neutral-500"
                      aria-hidden="true"
                    >
                      ↗
                    </span>
                    <strong className="text-sm font-semibold">
                      {suggestion.title}
                    </strong>
                    <small className="mt-1.5 text-[0.78rem] leading-snug text-neutral-500 dark:text-neutral-400">
                      {suggestion.description}
                    </small>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto mt-[18px] mb-[30px] w-[min(760px,calc(100%-28px))] md:w-[min(760px,calc(100%-40px))]">
              {messages.map((message) => (
                <article
                  className={`mb-[30px] flex gap-3.5 leading-relaxed ${
                    message.role === "user" ? "justify-end" : "justify-start"
                  }`}
                  key={message.id}
                >
                  {message.role === "assistant" && (
                    <span className="mt-0.5 grid size-[30px] shrink-0 place-items-center rounded-[9px] bg-emerald-600 text-xs font-extrabold text-white dark:bg-emerald-500">
                      D
                    </span>
                  )}
                  <div
                    className={
                      message.role === "user"
                        ? "max-w-[78%] rounded-[18px] bg-neutral-100 px-4 py-2.5 dark:bg-neutral-800"
                        : "min-w-0"
                    }
                  >
                    {message.role === "assistant" && (
                      <span className="mb-1 block text-[0.79rem] font-bold">
                        DocAlly
                      </span>
                    )}
                    <p className="m-0 text-[0.92rem]">{message.content}</p>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <div className="mx-auto w-[calc(100%-20px)] bg-white pt-2.5 pb-2.5 md:w-[min(800px,calc(100%-36px))] dark:bg-[#212121]">
          <form
            className="flex items-end gap-2 rounded-[25px] border border-neutral-300 bg-white px-2.5 py-2 shadow-[0_8px_30px_rgb(0_0_0_/_8%)] dark:border-neutral-600 dark:bg-neutral-800 dark:shadow-[0_8px_30px_rgb(0_0_0_/_30%)]"
            onSubmit={submitMessage}
          >
            <input
              ref={fileInputRef}
              className="sr-only"
              type="file"
              accept="application/pdf"
              aria-label="Chọn tài liệu PDF"
            />
            <button
              className={`grid size-[34px] shrink-0 place-items-center rounded-full bg-transparent text-xl font-light text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-700 ${focusRing}`}
              type="button"
              aria-label="Đính kèm tài liệu PDF"
              title="Đính kèm PDF"
              onClick={() => fileInputRef.current?.click()}
            >
              ＋
            </button>
            <textarea
              className="max-h-36 min-h-6 flex-1 resize-none overflow-y-auto border-0 bg-transparent px-1 py-1.5 text-[0.92rem] leading-6 text-neutral-900 outline-none placeholder:text-neutral-500 dark:text-neutral-100"
              value={input}
              rows={1}
              placeholder="Hỏi bất kỳ điều gì về tài liệu của bạn"
              aria-label="Nội dung câu hỏi"
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
            />
            <button
              className={`grid size-[34px] shrink-0 place-items-center rounded-full bg-neutral-900 text-lg font-bold text-white transition disabled:cursor-default disabled:opacity-20 dark:bg-white dark:text-neutral-900 ${focusRing}`}
              type="submit"
              aria-label="Gửi câu hỏi"
              disabled={!input.trim()}
            >
              ↑
            </button>
          </form>
          <p className="mt-1.5 mb-0 text-center text-[0.61rem] text-neutral-500 md:text-[0.68rem] dark:text-neutral-400">
            DocAlly có thể mắc lỗi. Hãy kiểm tra lại các trích dẫn quan trọng.
          </p>
        </div>
      </main>
    </div>
  );
}
