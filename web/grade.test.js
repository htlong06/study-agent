// Kiểm thử M8. Chạy: node --test web/
// M8-01..M8-06 là hàm thuần (Node). M8-07..M8-10 chạy trang thật bằng Playwright nếu có; không có thì bỏ qua.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { grade, dayStatus, validateQuizShape, shuffleQuestion } = require("./grade.js");

function makeQuiz(n, extra) {
  const questions = [];
  for (let i = 1; i <= n; i++) {
    questions.push({
      id: "q" + i, question: "Câu hỏi " + i + "?", options: ["A" + i, "B" + i, "C" + i, "D" + i],
      answer_index: i % 4, explanation: "Giải thích " + i,
      source: { file: "101-giai-tich-2/555-chuong-3.pdf", quote: "Trích dẫn " + i },
    });
  }
  return Object.assign({
    course_id: 101, course: "Giải tích 2", topic: "Tích phân bội", generated_at: "2026-10-29T00:05:00+00:00",
    model: "gemini-2.5-flash", pass_ratio: 0.7, questions,
  }, extra || {});
}
const answersFor = (quiz, wrongIds) => Object.fromEntries(quiz.questions.map((q) =>
  [q.id, (wrongIds || []).includes(q.id) ? (q.answer_index + 1) % 4 : q.answer_index]));

test("M8-01 trả lời đúng hết", () => {
  const quiz = makeQuiz(8);
  const r = grade(quiz, answersFor(quiz));
  assert.deepEqual(r, { correct: 8, total: 8, ratio: 1, passed: true, wrong: [] });
});

test("M8-02 câu sai và câu bỏ trống đều tính sai", () => {
  const quiz = makeQuiz(5);
  const answers = answersFor(quiz, ["q2"]);
  delete answers.q4;
  const r = grade(quiz, answers);
  assert.equal(r.correct, 3);
  assert.deepEqual(r.wrong, ["q2", "q4"]);
  assert.equal(r.passed, false);
  assert.deepEqual(grade(quiz, undefined).wrong, ["q1", "q2", "q3", "q4", "q5"]);
});

test("M8-03 ngưỡng 0.7: 7/10 đạt, 6/10 không đạt", () => {
  const quiz = makeQuiz(10);
  assert.equal(grade(quiz, answersFor(quiz, ["q1", "q2", "q3"])).passed, true);
  assert.equal(grade(quiz, answersFor(quiz, ["q1", "q2", "q3", "q4"])).passed, false);
  // các ngưỡng dễ lỗi số thực
  for (const [n, ok, ratio] of [[10, 7, 0.7], [100, 70, 0.7], [3, 2, 2 / 3], [5, 3, 0.6]]) {
    const qz = makeQuiz(n, { pass_ratio: ratio });
    const wrong = qz.questions.slice(0, n - ok).map((q) => q.id);
    assert.equal(grade(qz, answersFor(qz, wrong)).passed, true, n + " câu, đúng " + ok);
  }
});

test("M8-03 quiz rỗng không bao giờ đạt", () => {
  const r = grade(makeQuiz(0), {});
  assert.equal(r.passed, false);
  assert.equal(r.ratio, 0);
});

test("M8-04 dayStatus khi đủ và khi thiếu kết quả", () => {
  const today = { date: "2026-10-29", quizzes: ["quiz-101.json", "quiz-102.json"] };
  assert.deepEqual(dayStatus(today, { 101: { ratio: 0.8, passed: true }, 102: { ratio: 1, passed: true } }), { done: true, pending: [] });
  assert.deepEqual(dayStatus(today, { 101: { ratio: 0.8, passed: true } }), { done: false, pending: [102] });
  assert.deepEqual(dayStatus(today, { 101: { ratio: 0.8, passed: true }, 102: { ratio: 0.5, passed: false } }), { done: false, pending: [102] });
  assert.deepEqual(dayStatus(today, {}), { done: false, pending: [101, 102] });
  assert.deepEqual(dayStatus({ date: "2026-10-29", quizzes: [] }, {}), { done: true, pending: [] });
});

test("M8-05 validateQuizShape với quiz đúng và quiz sai", () => {
  assert.deepEqual(validateQuizShape(makeQuiz(3)), { ok: true });
  const cases = [
    [(q) => { q.questions[1].options.pop(); }, "questions[1].options"],
    [(q) => { q.questions[0].answer_index = 4; }, "questions[0].answer_index"],
    [(q) => { q.questions[2].id = "q1"; }, "trùng"],
    [(q) => { delete q.course_id; }, "course_id"],
    [(q) => { q.pass_ratio = 0; }, "pass_ratio"],
    [(q) => { q.questions = []; }, "questions"],
    [(q) => { delete q.questions[0].source; }, "source"],
    [(q) => { q.generated_at = "hôm qua"; }, "generated_at"],
  ];
  for (const [mutate, field] of cases) {
    const quiz = makeQuiz(3);
    mutate(quiz);
    const r = validateQuizShape(quiz);
    assert.equal(r.ok, false, field);
    assert.ok(r.error.includes(field), r.error + " phải nêu " + field);
  }
  assert.equal(validateQuizShape(null).ok, false);
  assert.equal(validateQuizShape([]).ok, false);
});

test("M8-06 xáo lựa chọn nhiều lần, đáp án đúng luôn trỏ đúng lựa chọn gốc", () => {
  const q = makeQuiz(4).questions[2];
  const original = q.options[q.answer_index];
  let seed = 7;
  const rng = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
  const orders = new Set();
  for (let i = 0; i < 300; i++) {
    const s = shuffleQuestion(q, i % 2 ? rng : undefined);
    assert.equal(s.options[s.answer_index], original);
    assert.deepEqual([...s.options].sort(), [...q.options].sort());
    orders.add(s.options.join("|"));
  }
  assert.ok(orders.size > 1, "phải có nhiều thứ tự khác nhau");
  assert.equal(q.options[q.answer_index], original, "không sửa câu hỏi gốc");
});

// ---- Kiểm thử trang thật (M8-07..M8-10) ----
let chromium = null;
try { chromium = require("playwright").chromium; } catch (e) { /* không có Playwright */ }
const skipUi = chromium ? false : "cần Playwright (npm i playwright) để chạy kiểm thử giao diện";
const PAGE = "file://" + path.resolve(__dirname, "quiz.html");

async function withPage(opts, fn) {
  const browser = await chromium.launch();
  const page = await (await browser.newContext()).newPage();
  const problems = [];
  page.on("console", (m) => { if (m.type() === "error") problems.push("console: " + m.text()); });
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
  page.on("dialog", (d) => { problems.push("dialog: " + d.message()); d.dismiss(); });
  if (opts.initScript) await page.addInitScript(opts.initScript);
  try {
    await page.goto(PAGE);
    await fn(page, problems);
  } finally {
    await browser.close();
  }
}
const jsonFile = (name, data) => ({ name, mimeType: "application/json", buffer: Buffer.from(JSON.stringify(data)) });

// Làm hết một quiz bằng cách luôn chọn đáp án có chữ của đáp án đúng gốc (đọc từ nhãn nút).
async function finishQuiz(page, quiz, mode) {
  for (let i = 0; i < quiz.questions.length; i++) {
    const q = quiz.questions[i];
    await page.getByText("Câu " + (i + 1) + " / " + quiz.questions.length).waitFor();
    const text = mode === "wrong" ? q.options[(q.answer_index + 1) % 4] : q.options[q.answer_index];
    await page.locator("button", { hasText: new RegExp("^[A-D]\\. " + text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "$") }).click();
    await page.getByRole("button", { name: i === quiz.questions.length - 1 ? "Xem kết quả" : "Câu tiếp" }).click();
  }
}

test("M8-07 nạp bộ fixture, làm hết một quiz, không lỗi console, hiện điểm cuối bài", { skip: skipUi }, async () => {
  const quiz = makeQuiz(4);
  const today = { date: "2026-10-29", timezone: "Asia/Ho_Chi_Minh", pass_ratio: 0.7, sessions: [], quizzes: ["quiz-101.json"] };
  await withPage({}, async (page, problems) => {
    await page.setInputFiles("#file-input", [jsonFile("today.json", today), jsonFile("quiz-101.json", quiz)]);
    await page.getByRole("button", { name: /Giải tích 2/ }).click();
    await finishQuiz(page, quiz, "right");
    await page.getByText("4 / 4").waitFor();
    await page.getByText("Hôm nay đã xong").first().waitFor();
    assert.equal(await page.evaluate(() => localStorage.getItem("study-agent.done.2026-10-29")), "1");
    const saved = JSON.parse(await page.evaluate(() => localStorage.getItem("study-agent.result.2026-10-29.101")));
    assert.equal(saved.passed, true);
    assert.equal(saved.ratio, 1);
    assert.deepEqual(problems, []);
  });
});

test("M8-07 làm sai nhiều: không đạt, liệt kê câu sai, làm lại được, lần fail không ghi đè lần đạt", { skip: skipUi }, async () => {
  const quiz = makeQuiz(4);
  const today = { date: "2026-10-29", quizzes: ["quiz-101.json"] };
  await withPage({}, async (page, problems) => {
    await page.setInputFiles("#file-input", [jsonFile("today.json", today), jsonFile("quiz-101.json", quiz)]);
    await page.getByRole("button", { name: /Giải tích 2/ }).click();
    await finishQuiz(page, quiz, "wrong");
    await page.getByText("0 / 4").waitFor();
    await page.getByText("Các câu cần xem lại").waitFor();
    assert.equal(await page.getByText("Hôm nay đã xong").count(), 0);
    await page.getByRole("button", { name: "Làm lại" }).click();
    await finishQuiz(page, quiz, "right");
    await page.getByText("4 / 4").waitFor();
    await page.getByRole("button", { name: "Làm lại" }).click();
    await finishQuiz(page, quiz, "wrong");
    await page.getByText("0 / 4").waitFor();
    const saved = JSON.parse(await page.evaluate(() => localStorage.getItem("study-agent.result.2026-10-29.101")));
    assert.equal(saved.passed, true);
    assert.deepEqual(problems, []);
  });
});

test("M8-08 today.json nêu quiz chưa được chọn: báo đúng tên file còn thiếu", { skip: skipUi }, async () => {
  const today = { date: "2026-10-29", quizzes: ["quiz-101.json", "quiz-102.json"] };
  await withPage({}, async (page, problems) => {
    await page.setInputFiles("#file-input", [jsonFile("today.json", today), jsonFile("quiz-101.json", makeQuiz(2))]);
    const alert = page.getByRole("alert").first();
    await alert.waitFor();
    const text = await alert.innerText();
    assert.ok(text.includes("quiz-102.json"), text);
    assert.ok(!text.includes("quiz-101.json"), text);
    assert.deepEqual(problems, []);
  });
});

test("M8-08 file quiz sai cấu trúc: báo lỗi nêu trường", { skip: skipUi }, async () => {
  const bad = makeQuiz(2);
  bad.questions[0].options.pop();
  await withPage({}, async (page) => {
    await page.setInputFiles("#file-input", [jsonFile("quiz-101.json", bad)]);
    const text = await page.getByRole("alert").first().innerText();
    assert.ok(text.includes("quiz-101.json") && text.includes("options"), text);
  });
});

test("M8-09 localStorage ném lỗi: trang vẫn chạy được", { skip: skipUi }, async () => {
  const quiz = makeQuiz(3);
  const today = { date: "2026-10-29", quizzes: ["quiz-101.json"] };
  const initScript = () => {
    Object.defineProperty(window, "localStorage", { get() { throw new DOMException("bị chặn", "SecurityError"); } });
  };
  await withPage({ initScript }, async (page, problems) => {
    await page.setInputFiles("#file-input", [jsonFile("today.json", today), jsonFile("quiz-101.json", quiz)]);
    await page.getByRole("button", { name: /Giải tích 2/ }).click();
    await finishQuiz(page, quiz, "right");
    await page.getByText("3 / 3").waitFor();
    await page.getByText("Hôm nay đã xong").first().waitFor();
    assert.deepEqual(problems, []);
  });
});

test("M8-10 câu hỏi chứa mã HTML hiển thị như chữ, không chạy mã", { skip: skipUi }, async () => {
  const quiz = makeQuiz(2);
  const evil = "<img src=x onerror=alert(1)>";
  quiz.questions[0].question = evil;
  quiz.questions[0].options[0] = evil + " A";
  quiz.questions[0].explanation = "<script>alert(2)</script>";
  quiz.questions[0].source.quote = "<b>đậm</b>";
  quiz.course = "<i>Môn</i>";
  const today = { date: "2026-10-29", quizzes: ["quiz-101.json"] };
  await withPage({}, async (page, problems) => {
    await page.setInputFiles("#file-input", [jsonFile("today.json", today), jsonFile("quiz-101.json", quiz)]);
    await page.getByRole("button", { name: /Môn/ }).click();
    await page.getByRole("heading", { name: evil }).waitFor();
    assert.equal(await page.locator("#app img, #app script, #app b, #app i").count(), 0);
    await page.locator("button").first().click();
    await page.waitForTimeout(200);
    assert.equal(await page.locator("#app img, #app script, #app b").count(), 0);
    assert.deepEqual(problems, []);
  });
});
