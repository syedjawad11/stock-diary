/* Stock Diary: language strings, unit words, sample sentences.
   Plain data only — no DOM work here. Loaded before app.js as a classic
   (non-module) script, so these top-level consts are visible to app.js. */

const STRINGS = {
  en: {
    appTitle: "Stock Diary",
    langEnglish: "English",
    langUrdu: "اردو",
    subtitle: "Your private demo",
    reset: "Reset",
    resetConfirm: "Reset your demo stock? This clears your entries and brings back the starting stock.",
    entryHeading: "What came in or went out?",
    entryPlaceholder: "e.g. 20 carton basmati aaye, 5 nikle",
    tryExample: "Try an example",
    checkEntry: "Check entry",
    checking: "Reading your entry… Gemma is reading, this can take up to 20 seconds.",
    quotaText: "{used} of {limit} checks used today",
    proposalsHeading: "Check before saving",
    directionIn: "In",
    directionOut: "Out",
    stockWord: "Stock",
    problemUnknownProduct: "Pick which product this is",
    problemInsufficientStock: "Not enough stock for this",
    problemUnitMismatch: "Unit doesn't match this product",
    selectProduct: "Select product…",
    cancel: "Cancel",
    confirmSave: "Confirm & save",
    confirming: "Saving…",
    savedToast: "Saved just now",
    undo: "Undo",
    undoing: "Undoing…",
    stockHeading: "Current stock",
    low: "LOW",
    askHeading: "Ask about your stock",
    askPlaceholder: "e.g. Kis cheez ka stock kam hai?",
    chipLowStock: "Low stock",
    chipToday: "Today",
    askButton: "Ask",
    asking: "Thinking…",
    recentHeading: "Recent entries",
    recentEmpty: "No entries yet.",
    reversalNote: "reversal",
    footer: "Runs on Gemma, an open-weight model. Demo data is made up.",
    errorNetwork: "Couldn't reach the server. Check your connection and try again.",
    retry: "Try again",
    errorGeneric: "Something went wrong.",
    noProposals: "Couldn't find anything to save in that. Try describing it differently.",
    confirmDisabledHint: "Fix the marked items before saving.",
    rateLimited: "You've used today's checks. Try again tomorrow.",
    movementIn: "In",
    movementOut: "Out",
  },
  ur: {
    appTitle: "اسٹاک ڈائری",
    langEnglish: "English",
    langUrdu: "اردو",
    subtitle: "آپ کا ذاتی ڈیمو",
    reset: "ریسٹ",
    resetConfirm: "اپنا ڈیمو اسٹاک ریسٹ کریں؟ اس سے آپ کے اندراجات مٹ جائیں گے اور ابتدائی اسٹاک واپس آ جائے گا۔",
    entryHeading: "کیا آیا یا گیا؟",
    entryPlaceholder: "مثلاً 20 کارٹن باسمتی آئے، 5 نکلے",
    tryExample: "ایک مثال آزمائیں",
    checkEntry: "اندراج چیک کریں",
    checking: "آپ کا اندراج پڑھا جا رہا ہے… جیما پڑھ رہا ہے، اس میں 20 سیکنڈ تک لگ سکتے ہیں۔",
    quotaText: "آج {used} میں سے {limit} چیک استعمال ہوئے",
    proposalsHeading: "محفوظ کرنے سے پہلے چیک کریں",
    directionIn: "آیا",
    directionOut: "گیا",
    stockWord: "اسٹاک",
    problemUnknownProduct: "یہ کون سی چیز ہے، منتخب کریں",
    problemInsufficientStock: "اس کے لیے اسٹاک کم ہے",
    problemUnitMismatch: "یونٹ اس چیز سے میل نہیں کھاتا",
    selectProduct: "چیز منتخب کریں…",
    cancel: "منسوخ کریں",
    confirmSave: "تصدیق اور محفوظ کریں",
    confirming: "محفوظ ہو رہا ہے…",
    savedToast: "ابھی محفوظ ہوا",
    undo: "واپس کریں",
    undoing: "واپس ہو رہا ہے…",
    stockHeading: "موجودہ اسٹاک",
    low: "کم",
    askHeading: "اپنے اسٹاک کے بارے میں پوچھیں",
    askPlaceholder: "مثلاً کس چیز کا اسٹاک کم ہے؟",
    chipLowStock: "کم اسٹاک",
    chipToday: "آج",
    askButton: "پوچھیں",
    asking: "سوچ رہا ہے…",
    recentHeading: "حالیہ اندراجات",
    recentEmpty: "ابھی تک کوئی اندراج نہیں۔",
    reversalNote: "واپسی",
    footer: "یہ جیما پر چلتا ہے، ایک اوپن ویٹ ماڈل۔ ڈیمو ڈیٹا فرضی ہے۔",
    errorNetwork: "سرور تک رسائی نہیں ہو سکی۔ اپنا کنکشن چیک کریں اور دوبارہ کوشش کریں۔",
    retry: "دوبارہ کوشش کریں",
    errorGeneric: "کچھ غلط ہو گیا۔",
    noProposals: "اس میں محفوظ کرنے کے لیے کچھ نہیں ملا۔ مختلف انداز میں لکھ کر دیکھیں۔",
    confirmDisabledHint: "محفوظ کرنے سے پہلے نشان زدہ چیزیں درست کریں۔",
    rateLimited: "آج کے چیک ختم ہو گئے۔ کل دوبارہ کوشش کریں۔",
    movementIn: "آیا",
    movementOut: "گیا",
  },
};

// Unit word map: English plural-ish + Urdu word, per product unit.
const UNITS = {
  carton: { en: "carton", en_plural: "cartons", ur: "کارٹن" },
  bag: { en: "bag", en_plural: "bags", ur: "بوری" },
  tin: { en: "tin", en_plural: "tins", ur: "ٹین" },
  packet: { en: "packet", en_plural: "packets", ur: "پیکٹ" },
  sack: { en: "sack", en_plural: "sacks", ur: "بوری" },
  box: { en: "box", en_plural: "boxes", ur: "ڈبہ" },
};

function unitLabel(unit, lang, qty) {
  if (!unit) return "";
  const u = UNITS[unit];
  if (!u) return unit;
  if (lang === "ur") return u.ur;
  return qty === 1 ? u.en : u.en_plural;
}

// Four sample sentences the "Try an example" button cycles through:
// English, Roman Urdu, Urdu script, mixed.
const EXAMPLE_SENTENCES = [
  "20 cartons of basmati came in, 5 went out",
  "20 carton basmati aaye, 5 nikle",
  "20 کارٹن باسمتی آئے، 5 نکلے",
  "5 bags laal mirch nikle aur 10 carton basmati aaye",
];

function t(lang, key, vars) {
  const dict = STRINGS[lang] || STRINGS.en;
  let s = dict[key];
  if (s === undefined) s = (STRINGS.en[key] !== undefined) ? STRINGS.en[key] : key;
  if (vars) {
    Object.keys(vars).forEach(function (k) {
      s = s.split("{" + k + "}").join(String(vars[k]));
    });
  }
  return s;
}
