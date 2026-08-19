// 営業進捗報告テンプレートの「フォーム送信：」項目に自動集計値を埋め込むための参照先
const SALES_SUMMARY_SPREADSHEET_ID = "1rL8R3WOPBSJ2WRgziUS2lbLinAs4n0hhCOEc3YEoYvY";
const SALES_SUMMARY_SHEET_NAME = "完了件数集計";

function doGet(e) {
  const p = e.parameter;

  const type       = p.type        || "";
  const member     = p.member      || "";
  const channel    = p.channel     || "";
  const subChannel = p.sub_channel || "";
  const timestamp  = p.timestamp   || "";
  const messageUrl = p.message_url || "";

  if (type === "sales_summary") {
    return getSalesSummary();
  }

  if (type === "attendance") {
    recordAttendance({
      member,
      channel,
      subChannel,
      loginTime: p.login_time || "",
      timestamp,
      messageUrl,
    });
  } else if (type === "report") {
    recordReport({
      member,
      channel,
      subChannel,
      date:   p.date   || "",
      count:  Number(p.count  || 0),
      rate:   Number(p.rate   || 0),
      reward: Number(p.reward || 0),
      notes:  p.notes  || "",
      other:  p.other  || "",
      timestamp,
      messageUrl,
    });
  } else if (type === "hybrid_report") {
    // CORDER・Composure架電など：日額固定＋残業時間割のハイブリッド単価。
    // 単一の単価に落とし込めないため単価欄は空にし、内訳を伝達事項に記載する。
    // 既存の「報告」シートにそのまま記録し、報酬計算・メンバー別集計への反映は
    // 既存の仕組み（既存シートを参照する集計）に委ねる。新しいシートは作らない。
    const workedHours  = Number(p.worked_hours  || 0);
    const normalCost   = Number(p.normal_cost   || 0);
    const overtimeCost = Number(p.overtime_cost || 0);
    const reward       = Number(p.reward        || 0);
    const revenue      = Number(p.revenue       || 0);
    const breakdown = `実働${workedHours}h（通常${normalCost}円＋残業${overtimeCost}円＝${reward}円）`;

    recordReport({
      member,
      channel,
      subChannel,
      date:   p.date || "",
      count:  workedHours,
      rate:   "",
      reward,
      notes:  p.notes ? `${p.notes}\n${breakdown}` : breakdown,
      other:  `売上${revenue}円`,
      timestamp,
      messageUrl,
    });
  } else {
    return ContentService.createTextOutput("unknown type: " + type);
  }

  return ContentService.createTextOutput("ok");
}

function getSalesSummary() {
  const ss = SpreadsheetApp.openById(SALES_SUMMARY_SPREADSHEET_ID);
  const sheet = ss.getSheetByName(SALES_SUMMARY_SHEET_NAME);
  if (!sheet) {
    return jsonOutput({ error: "sheet not found: " + SALES_SUMMARY_SHEET_NAME });
  }

  const values = sheet.getDataRange().getValues();

  // 「対応者 / リスト作成件数 / フォーム送信件数（送信済みのみ）」のヘッダー行を探す
  // （説明文などが上に入っていても対応できるよう、位置固定にしない）
  let headerRow = -1;
  let colList = -1;
  let colForm = -1;
  for (let r = 0; r < values.length; r++) {
    const row = values[r];
    const idxList = row.indexOf("リスト作成件数");
    const idxForm = row.findIndex(v => typeof v === "string" && v.indexOf("フォーム送信件数") === 0);
    if (idxList !== -1 && idxForm !== -1) {
      headerRow = r;
      colList = idxList;
      colForm = idxForm;
      break;
    }
  }

  if (headerRow === -1) {
    return jsonOutput({ error: "header row not found" });
  }

  let listTotal = 0;
  let formTotal = 0;
  for (let r = headerRow + 1; r < values.length; r++) {
    const person = values[r][0];
    if (!person || person === "合計") continue; // 集計済みの合計行は二重加算しない
    listTotal += Number(values[r][colList]) || 0;
    formTotal += Number(values[r][colForm]) || 0;
  }

  return jsonOutput({ list_count: listTotal, form_count: formTotal });
}

function jsonOutput(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function recordReport(d) {
  const ss    = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("報告") || ss.getActiveSheet();

  // ヘッダーがなければ1行目に追加
  if (sheet.getLastRow() === 0) {
    sheet.appendRow([
      "タイムスタンプ", "メンバー", "チャンネル", "サブチャンネル",
      "日付", "件数", "単価", "報酬", "伝達事項", "その他", "メッセージURL"
    ]);
  }

  sheet.appendRow([
    d.timestamp,
    d.member,
    d.channel,
    d.subChannel,
    d.date,
    d.count,
    d.rate,
    d.reward,
    d.notes,
    d.other,
    d.messageUrl,
  ]);
}

function recordAttendance(d) {
  const ss    = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("勤怠") || ss.getActiveSheet();

  // ヘッダーがなければ1行目に追加
  if (sheet.getLastRow() === 0) {
    sheet.appendRow([
      "タイムスタンプ", "メンバー", "チャンネル", "ログイン時刻", "メッセージURL"
    ]);
  }

  sheet.appendRow([
    d.timestamp,
    d.member,
    d.channel,
    d.loginTime,
    d.messageUrl,
  ]);
}
