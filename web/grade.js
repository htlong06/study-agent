/* M8: hàm thuần chấm quiz. Dùng được trong trình duyệt (window.StudyGrade) và Node (module.exports). */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.StudyGrade = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var EPS = 1e-9; // tránh lỗi làm tròn số thực: 7/10 so với 0.7

  // answers: { "q1": 2, ... }; câu chưa trả lời tính là sai
  function grade(quiz, answers) {
    var questions = quiz.questions || [];
    var given = answers || {};
    var correct = 0;
    var wrong = [];
    questions.forEach(function (q) {
      if (given[q.id] === q.answer_index) correct += 1;
      else wrong.push(q.id);
    });
    var total = questions.length;
    var passRatio = typeof quiz.pass_ratio === "number" ? quiz.pass_ratio : 0.7;
    return {
      correct: correct,
      total: total,
      ratio: total ? correct / total : 0,
      passed: total > 0 && correct + EPS >= passRatio * total,
      wrong: wrong,
    };
  }

  // "quiz-101.json" -> 101; không khớp thì trả null
  function courseIdFromFile(name) {
    var m = /^quiz-(\d+)\.json$/.exec(String(name));
    return m ? Number(m[1]) : null;
  }

  // results: { [courseId]: { ratio, passed } }; done khi mọi quiz trong today.quizzes đã đạt
  function dayStatus(today, results) {
    var have = results || {};
    var pending = [];
    (today.quizzes || []).forEach(function (file) {
      var id = courseIdFromFile(file);
      if (id === null || !have[id] || !have[id].passed) pending.push(id === null ? file : id);
    });
    return { done: pending.length === 0, pending: pending };
  }

  function validateQuizShape(quiz) {
    function bad(msg) { return { ok: false, error: msg }; }
    if (!quiz || typeof quiz !== "object" || Array.isArray(quiz)) return bad("quiz: phải là một đối tượng JSON");
    if (!Number.isInteger(quiz.course_id)) return bad("quiz.course_id: thiếu hoặc không phải số nguyên");
    var keys = ["course", "topic", "model"];
    for (var k = 0; k < keys.length; k++) {
      if (typeof quiz[keys[k]] !== "string") return bad("quiz." + keys[k] + ": thiếu hoặc không phải chuỗi");
    }
    if (typeof quiz.generated_at !== "string" || isNaN(Date.parse(quiz.generated_at))) {
      return bad("quiz.generated_at: thiếu hoặc không phải thời gian ISO 8601");
    }
    if (typeof quiz.pass_ratio !== "number" || !(quiz.pass_ratio > 0 && quiz.pass_ratio <= 1)) {
      return bad("quiz.pass_ratio: phải là số trong khoảng (0, 1]");
    }
    if (!Array.isArray(quiz.questions) || quiz.questions.length === 0) return bad("quiz.questions: phải là danh sách không rỗng");
    var seen = {};
    for (var i = 0; i < quiz.questions.length; i++) {
      var q = quiz.questions[i];
      var where = "quiz.questions[" + i + "]";
      if (!q || typeof q !== "object") return bad(where + ": phải là một đối tượng");
      if (typeof q.id !== "string" || !q.id) return bad(where + ".id: thiếu hoặc không phải chuỗi");
      if (seen[q.id]) return bad(where + ".id: '" + q.id + "' bị trùng");
      seen[q.id] = true;
      if (typeof q.question !== "string" || !q.question) return bad(where + ".question: thiếu");
      if (typeof q.explanation !== "string") return bad(where + ".explanation: thiếu");
      if (!Array.isArray(q.options) || q.options.length !== 4 ||
          !q.options.every(function (o) { return typeof o === "string" && o.trim(); })) {
        return bad(where + ".options: phải đúng 4 chuỗi không rỗng");
      }
      if (!Number.isInteger(q.answer_index) || q.answer_index < 0 || q.answer_index > 3) {
        return bad(where + ".answer_index: phải là số nguyên từ 0 đến 3");
      }
      if (!q.source || typeof q.source.file !== "string" || typeof q.source.quote !== "string") {
        return bad(where + ".source: thiếu file hoặc quote");
      }
    }
    return { ok: true };
  }

  // Xáo thứ tự lựa chọn; answer_index được tính lại để vẫn trỏ đúng lựa chọn gốc.
  function shuffleQuestion(q, rng) {
    var random = rng || Math.random;
    var order = [0, 1, 2, 3];
    for (var i = order.length - 1; i > 0; i--) {
      var j = Math.floor(random() * (i + 1));
      var t = order[i]; order[i] = order[j]; order[j] = t;
    }
    var copy = {};
    Object.keys(q).forEach(function (key) { copy[key] = q[key]; });
    copy.options = order.map(function (o) { return q.options[o]; });
    copy.answer_index = order.indexOf(q.answer_index);
    return copy;
  }

  return {
    grade: grade,
    dayStatus: dayStatus,
    validateQuizShape: validateQuizShape,
    shuffleQuestion: shuffleQuestion,
    courseIdFromFile: courseIdFromFile,
  };
});
