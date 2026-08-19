// 営業進捗報告テンプレートの自動集計項目の参照先（「営業リスト・送信管理」シートから直接集計する）
const SALES_SUMMARY_SPREADSHEET_ID = "1G1Zo4eBYp77R7gFckV-TZNY5qF-p_ZcMYY6BUK8xKYg";
const SALES_LIST_SHEET_NAME = "営業リスト・送信管理";
const SALES_SENT_STATUS = "送信済み";
const SALES_REPLY_YES = "あり";
const SALES_NEGOTIATION_YES = "あり";
const SALES_DEAL_RESULT = "成約";
const SALES_GOAL_COUNT = 5000; // 目標件数（コード内固定値）

// 報告・勤怠の記録先は必ずシート名で指定する（getActiveSheet()にフォールバックしない）。
// 正式な記録先は「シート1」（Discordメッセージへのリンク付きで情報量が多いため採用）。
const REPORT_SHEET_NAME = "シート1";
const ATTENDANCE_SHEET_NAME = "勤怠";

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
    if (!recordAttendance({
      member,
      channel,
      subChannel,
      loginTime: p.login_time || "",
      timestamp,
      messageUrl,
    })) {
      return ContentService.createTextOutput("error: sheet not found: " + ATTENDANCE_SHEET_NAME);
    }
  } else if (type === "report") {
    if (!recordReport({
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
    })) {
      return ContentService.createTextOutput("error: sheet not found: " + REPORT_SHEET_NAME);
    }
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

    if (!recordReport({
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
    })) {
      return ContentService.createTextOutput("error: sheet not found: " + REPORT_SHEET_NAME);
    }
  } else if (type === "fixed_fee") {
    // エアコン案件・株式会社sou・不動産cs-🏠など：固定報酬のため単価計算はせず、報告のみ記録する。
    // reward は常に0（実際の固定額の支払いはスプレッドシート側で別途・月次で行う）。
    if (!recordReport({
      member,
      channel,
      subChannel,
      date:   p.date || "",
      count:  Number(p.count || 0),
      rate:   "",
      reward: 0,
      notes:  p.notes || "",
      other:  p.group ? `グループ:${p.group}` : "",
      timestamp,
      messageUrl,
    })) {
      return ContentService.createTextOutput("error: sheet not found: " + REPORT_SHEET_NAME);
    }
  } else {
    return ContentService.createTextOutput("unknown type: " + type);
  }

  return ContentService.createTextOutput("ok");
}

function getSalesSummary() {
  const ss = SpreadsheetApp.openById(SALES_SUMMARY_SPREADSHEET_ID);
  const sheet = ss.getSheetByName(SALES_LIST_SHEET_NAME);
  if (!sheet) {
    return jsonOutput({ error: "sheet not found: " + SALES_LIST_SHEET_NAME });
  }

  const values = sheet.getDataRange().getValues();

  // 「企業名 / 送信ステータス / 返信 / 商談予定 / 結果」のヘッダー行を探す
  // （列の追加・並び替えに対応できるよう、位置固定にしない）
  let headerRow = -1;
  let colCompany = -1;
  let colStatus = -1;
  let colReply = -1;
  let colNegotiation = -1;
  let colResult = -1;
  for (let r = 0; r < values.length; r++) {
    const row = values[r];
    const idxCompany     = row.indexOf("企業名");
    const idxStatus      = row.indexOf("送信ステータス");
    const idxReply       = row.indexOf("返信");
    const idxNegotiation = row.indexOf("商談予定");
    const idxResult      = row.indexOf("結果");
    if (idxCompany !== -1 && idxStatus !== -1 && idxReply !== -1 && idxNegotiation !== -1 && idxResult !== -1) {
      headerRow = r;
      colCompany = idxCompany;
      colStatus = idxStatus;
      colReply = idxReply;
      colNegotiation = idxNegotiation;
      colResult = idxResult;
      break;
    }
  }

  if (headerRow === -1) {
    return jsonOutput({ error: "header row not found in " + SALES_LIST_SHEET_NAME });
  }

  let listTotal = 0;
  let sentCount = 0;
  let replyCount = 0;
  let negotiationCount = 0;
  let dealCount = 0;
  for (let r = headerRow + 1; r < values.length; r++) {
    const row = values[r];
    const company     = row[colCompany];
    const status      = String(row[colStatus] || "").trim();
    const reply       = String(row[colReply] || "").trim();
    const negotiation = String(row[colNegotiation] || "").trim();
    const result      = String(row[colResult] || "").trim();

    if (company) listTotal++;                            // リスト総数：企業名が入力済みの行数
    if (status === SALES_SENT_STATUS) sentCount++;        // 送信済み件数
    if (reply === SALES_REPLY_YES) replyCount++;          // 返信件数
    if (negotiation === SALES_NEGOTIATION_YES) negotiationCount++; // 商談予定件数
    if (result === SALES_DEAL_RESULT) dealCount++;        // 成約件数
  }

  const sentRate = listTotal > 0 ? Math.round((sentCount / listTotal) * 1000) / 10 : 0;
  const goalRate = Math.round((sentCount / SALES_GOAL_COUNT) * 1000) / 10;

  return jsonOutput({
    list_total: listTotal,
    sent_count: sentCount,
    sent_rate: sentRate,
    reply_count: replyCount,
    negotiation_count: negotiationCount,
    deal_count: dealCount,
    goal_count: SALES_GOAL_COUNT,
    goal_rate: goalRate,
  });
}

function jsonOutput(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function recordReport(d) {
  const ss    = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(REPORT_SHEET_NAME);
  if (!sheet) {
    Logger.log("recordReport: sheet not found: " + REPORT_SHEET_NAME);
    return false;
  }

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
  return true;
}

function recordAttendance(d) {
  const ss    = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(ATTENDANCE_SHEET_NAME);
  if (!sheet) {
    Logger.log("recordAttendance: sheet not found: " + ATTENDANCE_SHEET_NAME);
    return false;
  }

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
  return true;
}
