/**
 * FAPM 结构化问卷 — 前端逻辑
 *
 * 这版问卷以“家庭成员”为主表。
 * 第 2/3/6 部分均从第 1 部分自动同步成员名单，再分别录入收入、支出和保险信息。
 */

var _eventSeq = {};
var _phaseWeightsManuallyEdited = false;

var RISK_PHASE_TEMPLATES = {
  conservative: [
    { label: '近期 / Near', maxYears: 3, weights: [0.90, 0.05, 0.025, 0.025] },
    { label: '中期 / Mid', maxYears: 7, weights: [0.70, 0.20, 0.05, 0.05] },
    { label: '远期 / Long', maxYears: 10, weights: [0.50, 0.35, 0.075, 0.075] },
    { label: '超远期 / Ultra-long', maxYears: 99, weights: [0.35, 0.50, 0.075, 0.075] }
  ],
  balanced: [
    { label: '近期 / Near', maxYears: 3, weights: [0.875, 0.05, 0.025, 0.05] },
    { label: '中期 / Mid', maxYears: 7, weights: [0.60, 0.30, 0.075, 0.075] },
    { label: '远期 / Long', maxYears: 10, weights: [0.40, 0.45, 0.10, 0.10] },
    { label: '超远期 / Ultra-long', maxYears: 99, weights: [0.225, 0.575, 0.075, 0.125] }
  ],
  aggressive: [
    { label: '近期 / Near', maxYears: 3, weights: [0.85, 0.08, 0.02, 0.05] },
    { label: '中期 / Mid', maxYears: 7, weights: [0.50, 0.40, 0.05, 0.05] },
    { label: '远期 / Long', maxYears: 10, weights: [0.30, 0.55, 0.075, 0.075] },
    { label: '超远期 / Ultra-long', maxYears: 99, weights: [0.15, 0.70, 0.075, 0.075] }
  ]
};

function repeat(str, n) {
  var out = '';
  for (var i = 0; i < n; i++) out += str;
  return out;
}

function formatScalar(val) {
  if (typeof val === 'boolean') return val ? 'true' : 'false';
  if (typeof val === 'number') return String(val);
  if (typeof val === 'string') {
    if (/^\d+(\.\d+)?$/.test(val) || val === '') return '"' + val + '"';
    if (/[:#\[\]{}|>&*!,]/.test(val)) return '"' + val.replace(/"/g, '\\"') + '"';
    return '"' + val + '"';
  }
  return String(val);
}

function toYAML(obj, indent) {
  indent = indent || 0;
  var pad = repeat('  ', indent);
  var lines = [];

  if (Array.isArray(obj)) {
    if (obj.length === 0) return pad + '[]';
    if (obj.length === 2 && typeof obj[0] === 'number' && typeof obj[1] === 'number') {
      return '[' + obj[0] + ', ' + obj[1] + ']';
    }
    obj.forEach(function(item) {
      if (typeof item === 'object' && item !== null && !Array.isArray(item)) {
        var keys = Object.keys(item);
        keys.forEach(function(k, idx) {
          var prefix = idx === 0 ? pad + '- ' : pad + '  ';
          var val = item[k];
          if (typeof val === 'object' && val !== null) {
            if (Array.isArray(val) && val.length === 2 &&
                typeof val[0] === 'number' && typeof val[1] === 'number') {
              lines.push(prefix + k + ': ' + toYAML(val, 0));
            } else {
              lines.push(prefix + k + ':');
              lines.push(toYAML(val, indent + 2));
            }
          } else {
            lines.push(prefix + k + ': ' + formatScalar(val));
          }
        });
      } else {
        lines.push(pad + '- ' + formatScalar(item));
      }
    });
    return lines.join('\n');
  }

  if (typeof obj === 'object' && obj !== null) {
    Object.keys(obj).forEach(function(k) {
      var val = obj[k];
      if (val === null || val === undefined) return;
      if (typeof val === 'object') {
        if (Array.isArray(val)) {
          if (val.length === 0) return;
          if (val.length === 2 && typeof val[0] === 'number' && typeof val[1] === 'number') {
            lines.push(pad + k + ': ' + toYAML(val, 0));
          } else {
            lines.push(pad + k + ':');
            lines.push(toYAML(val, indent + 1));
          }
        } else if (Object.keys(val).length > 0) {
          lines.push(pad + k + ':');
          lines.push(toYAML(val, indent + 1));
        }
      } else {
        lines.push(pad + k + ': ' + formatScalar(val));
      }
    });
    return lines.join('\n');
  }

  return pad + formatScalar(obj);
}

function val(ctx, cls) {
  var el = ctx.querySelector ? ctx.querySelector('.' + cls) : ctx;
  return el ? el.value.trim() : '';
}

function numVal(ctx, cls) {
  var raw = cls ? val(ctx, cls) : ctx.value.trim();
  if (raw === '') return null;
  var n = Number(raw);
  return isNaN(n) ? null : n;
}

function floatVal(el) {
  if (!el) return null;
  var raw = el.value.trim();
  if (raw === '') return null;
  var n = parseFloat(raw);
  return isNaN(n) ? null : n;
}

function setVal(row, cls, value) {
  var el = row.querySelector('.' + cls);
  if (el) el.value = value;
}

function svi(id, value) {
  var el = document.getElementById(id);
  if (el) el.value = value;
}

function sviByClass(cls, value) {
  var el = document.querySelector('.' + cls);
  if (el) el.value = value;
}

function phaseFieldValue(idx, suffix) {
  var el = document.querySelector('.as-ph-' + idx + '-' + suffix);
  return floatVal(el);
}

function phaseMaxValue(idx) {
  var el = document.querySelector('.as-ph-max-' + idx);
  return numVal(el);
}

function formatPct(value) {
  return Math.round(value * 1000) / 10 + '%';
}

function renderRiskTemplateSummaries() {
  ['conservative', 'balanced', 'aggressive'].forEach(function(key) {
    var host = document.getElementById('risk-template-' + key);
    if (!host) return;
    var template = RISK_PHASE_TEMPLATES[key];
    host.innerHTML = template.map(function(item) {
      return item.label + '≤' + item.maxYears + '年: '
        + '固收/FI ' + formatPct(item.weights[0]) + ' / '
        + '权益/EQ ' + formatPct(item.weights[1]) + ' / '
        + '保险/INS ' + formatPct(item.weights[2]) + ' / '
        + '另类/ALT ' + formatPct(item.weights[3]);
    }).join('<br>');
  });
}

function applyRiskTemplate(riskKey, options) {
  options = options || {};
  var template = RISK_PHASE_TEMPLATES[riskKey];
  if (!template) return false;
  template.forEach(function(item, idx) {
    sviByClass('as-ph-max-' + idx, item.maxYears);
    sviByClass('as-ph-' + idx + '-fi', item.weights[0]);
    sviByClass('as-ph-' + idx + '-eq', item.weights[1]);
    sviByClass('as-ph-' + idx + '-ins', item.weights[2]);
    sviByClass('as-ph-' + idx + '-alt', item.weights[3]);
  });
  if (!options.preserveManualFlag) _phaseWeightsManuallyEdited = false;
  updatePhaseSyncStatus();
  return true;
}

function currentPhaseMatchesTemplate(riskKey) {
  var template = RISK_PHASE_TEMPLATES[riskKey];
  if (!template) return false;
  for (var idx = 0; idx < template.length; idx++) {
    var item = template[idx];
    if (phaseMaxValue(idx) !== item.maxYears) return false;
    if (phaseFieldValue(idx, 'fi') !== item.weights[0]) return false;
    if (phaseFieldValue(idx, 'eq') !== item.weights[1]) return false;
    if (phaseFieldValue(idx, 'ins') !== item.weights[2]) return false;
    if (phaseFieldValue(idx, 'alt') !== item.weights[3]) return false;
  }
  return true;
}

function updatePhaseSyncStatus() {
  var statusEl = document.getElementById('phase-sync-status');
  var resetBtn = document.getElementById('phase-reset-btn');
  var riskEl = document.getElementById('risk-tolerance');
  if (!statusEl || !riskEl) return;
  var riskLabelMap = {
    conservative: '保守 / Conservative',
    balanced: '平衡 / Balanced',
    aggressive: '进取 / Aggressive'
  };
  if (!riskEl.value) {
    statusEl.textContent = '当前未绑定风险偏好模板 / No risk template is currently linked.';
    if (resetBtn) resetBtn.disabled = true;
    return;
  }
  if (_phaseWeightsManuallyEdited) {
    statusEl.textContent = '第 8 部分的阶段权重已手动修改，当前不再自动跟随“' + riskLabelMap[riskEl.value] + '”模板 / Section 8 has been edited manually, so it no longer auto-follows the "' + riskLabelMap[riskEl.value] + '" template.';
    if (resetBtn) resetBtn.disabled = false;
    return;
  }
  statusEl.textContent = '第 8 部分的阶段权重当前跟随“' + riskLabelMap[riskEl.value] + '”模板 / Section 8 is currently following the "' + riskLabelMap[riskEl.value] + '" template.';
  if (resetBtn) resetBtn.disabled = false;
}

function syncRiskToPhasesIfAllowed() {
  var riskEl = document.getElementById('risk-tolerance');
  if (!riskEl || !riskEl.value) {
    updatePhaseSyncStatus();
    return;
  }
  if (_phaseWeightsManuallyEdited) {
    updatePhaseSyncStatus();
    return;
  }
  applyRiskTemplate(riskEl.value);
}

function markPhaseWeightsEdited() {
  var riskEl = document.getElementById('risk-tolerance');
  if (riskEl && riskEl.value && currentPhaseMatchesTemplate(riskEl.value)) {
    _phaseWeightsManuallyEdited = false;
  } else {
    _phaseWeightsManuallyEdited = true;
  }
  updatePhaseSyncStatus();
}

function clearRow(row) {
  row.querySelectorAll('input, select, textarea').forEach(function(el) {
    if (el.type === 'checkbox') el.checked = false;
    else el.value = '';
  });
}

function addRow(btn) {
  var list = btn.closest('.dynamic-list');
  var rows = list.querySelectorAll('.dynamic-row');
  var last = rows[rows.length - 1];
  if (!last) return;
  var clone = last.cloneNode(true);
  clearRow(clone);
  last.parentNode.insertBefore(clone, btn);
  bindStaticEvents();
  if (list.id === 'members-list') refreshMemberDrivenSections();
  updateFamilyTotals();
}

function removeRow(btn) {
  var row = btn.closest('.dynamic-row');
  var list = row.closest('.dynamic-list');
  var rows = list.querySelectorAll('.dynamic-row');
  if (rows.length <= 1) {
    clearRow(row);
  } else {
    row.remove();
  }
  if (list.id === 'members-list') refreshMemberDrivenSections();
  updateFamilyTotals();
}

function ensureRows(listSelector, count) {
  var list = document.querySelector(listSelector);
  if (!list) return;
  var rows = list.querySelectorAll('.dynamic-row');
  while (rows.length < count) {
    var addBtn = list.querySelector('.btn-add');
    if (!addBtn) break;
    addRow(addBtn);
    rows = list.querySelectorAll('.dynamic-row');
  }
}

function ensureExactDynamicRows(listSelector, count) {
  var list = document.querySelector(listSelector);
  if (!list) return;
  ensureRows(listSelector, count);
  var rows = list.querySelectorAll('.dynamic-row');
  while (rows.length > Math.max(count, 1)) {
    rows[rows.length - 1].remove();
    rows = list.querySelectorAll('.dynamic-row');
  }
  if (count === 0 && rows[0]) clearRow(rows[0]);
}

function ensureExactTableRows(tbodySelector, rowSelector, targetCount, addFn) {
  var tbody = document.querySelector(tbodySelector);
  if (!tbody) return;
  while (tbody.querySelectorAll(rowSelector).length < targetCount) addFn();
  var rows = tbody.querySelectorAll(rowSelector);
  while (rows.length > Math.max(targetCount, 1)) {
    rows[rows.length - 1].remove();
    rows = tbody.querySelectorAll(rowSelector);
  }
  if (targetCount === 0 && rows[0]) clearRow(rows[0]);
}

function addEventRow() {
  var tbody = document.getElementById('events-tbody');
  if (!tbody) return;
  var rows = tbody.querySelectorAll('.evt-row');
  var last = rows[rows.length - 1];
  if (!last) return;
  var clone = last.cloneNode(true);
  clearRow(clone);
  tbody.appendChild(clone);
  bindStaticEvents();
  syncSavingsDropdown();
}

function removeEventRow(btn) {
  var row = btn.closest('.evt-row');
  var tbody = row.closest('tbody');
  var rows = tbody.querySelectorAll('.evt-row');
  if (rows.length <= 1) {
    clearRow(row);
  } else {
    row.remove();
  }
  syncSavingsDropdown();
}

function addSavingsRow() {
  var tbody = document.getElementById('savings-tbody');
  if (!tbody) return;
  var rows = tbody.querySelectorAll('.sav-row');
  var last = rows[rows.length - 1];
  if (!last) return;
  var clone = last.cloneNode(true);
  clearRow(clone);
  tbody.appendChild(clone);
  syncSavingsDropdown();
}

function removeSavingsRow(btn) {
  var row = btn.closest('.sav-row');
  var tbody = row.closest('tbody');
  var rows = tbody.querySelectorAll('.sav-row');
  if (rows.length <= 1) {
    clearRow(row);
  } else {
    row.remove();
  }
}

function autoGenEventId(typeSel) {
  var row = typeSel.closest('.evt-row');
  var idInput = row.querySelector('.evt-id');
  if (!idInput || !typeSel.value || idInput.value) return;
  _eventSeq[typeSel.value] = (_eventSeq[typeSel.value] || 0) + 1;
  idInput.value = typeSel.value + '_' + String(_eventSeq[typeSel.value]).padStart(3, '0');
}

function syncSavingsDropdown() {
  var options = [];
  document.querySelectorAll('#events-tbody .evt-row').forEach(function(row) {
    var id = val(row, 'evt-id');
    if (!id) return;
    var label = val(row, 'evt-desc') || id;
    var year = val(row, 'evt-year');
    if (year) label += ' (' + year + '年)';
    options.push({ value: id, label: label });
  });
  options.push({ value: '富余资金', label: '富余资金 / Surplus Account' });

  document.querySelectorAll('#savings-tbody .sav-linked').forEach(function(sel) {
    var current = sel.value;
    sel.innerHTML = '';
    sel.appendChild(new Option('— 请选择 / Select —', ''));
    options.forEach(function(opt) {
      sel.appendChild(new Option(opt.label, opt.value));
    });
    if (current) sel.value = current;
  });
}

function getMembers() {
  var members = [];
  document.querySelectorAll('#members-list .dynamic-row').forEach(function(row, idx) {
    var name = val(row, 'member-name');
    if (!name) return;
    members.push({
      index: idx,
      name: name,
      age: numVal(row, 'member-age'),
      role: val(row, 'member-role'),
      retirementAge: numVal(row, 'member-retire-age')
    });
  });
  return members;
}

function readExistingRows(selector, rowClass, fieldClasses) {
  var rows = document.querySelectorAll(selector + ' .' + rowClass);
  return Array.prototype.map.call(rows, function(row) {
    var data = {};
    fieldClasses.forEach(function(cls) {
      data[cls] = val(row, cls);
    });
    return data;
  });
}

function syncIncomeRows() {
  var container = document.getElementById('income-rows');
  if (!container) return;
  var members = getMembers();
  var existing = readExistingRows('#income-rows', 'income-row', [
    'member-current-income',
    'member-income-start-age',
    'member-income-start-annual',
    'member-pension',
    'member-annuity'
  ]);
  var html = '<table class="form-table income-table">';
  html += '<tr><th class="align-left">成员 / Member</th><th>当前年收入(元) / Current annual income</th><th>开始收入年龄 / Income start age</th><th>未来年收入(元) / Future annual income</th><th>退休养老金(月) / Pension</th><th>退休年金(月) / Annuity</th></tr>';
  members.forEach(function(member, idx) {
    var old = existing[idx] || {};
    html += '<tr class="income-row">';
    html += '<td class="align-left"><strong>' + member.name + '</strong></td>';
    html += '<td><input type="number" class="member-current-income table-input-md" value="' + (old['member-current-income'] || '') + '" min="0" step="1000"></td>';
    html += '<td><input type="number" class="member-income-start-age table-input-sm" value="' + (old['member-income-start-age'] || '') + '" min="0" max="99" placeholder="如 / e.g. 22"></td>';
    html += '<td><input type="number" class="member-income-start-annual table-input-md" value="' + (old['member-income-start-annual'] || '') + '" min="0" step="1000" placeholder="未成年人/待就业成员可填 / optional for minors or not-yet-working members"></td>';
    html += '<td><input type="number" class="member-pension table-input-md" value="' + (old['member-pension'] || '') + '" min="0" step="100"></td>';
    html += '<td><input type="number" class="member-annuity table-input-md" value="' + (old['member-annuity'] || '') + '" min="0" step="100"></td>';
    html += '</tr>';
  });
  html += '</table>';
  container.innerHTML = html;
}

function syncExpenseRows() {
  var container = document.getElementById('expense-rows');
  if (!container) return;
  var members = getMembers();
  var existing = readExistingRows('#expense-rows', 'expense-row', [
    'member-expense',
    'member-retire-coeff'
  ]);
  var html = '<table class="form-table expense-table">';
  html += '<tr><th class="align-left">成员 / Member</th><th>当前月支出(元) / Current monthly spending</th><th>退休后支出系数 / Retirement factor</th></tr>';
  members.forEach(function(member, idx) {
    var old = existing[idx] || {};
    html += '<tr class="expense-row">';
    html += '<td class="align-left"><strong>' + member.name + '</strong></td>';
    html += '<td><input type="number" class="member-expense table-input-md" value="' + (old['member-expense'] || '') + '" min="0" step="100"></td>';
    html += '<td><input type="number" class="member-retire-coeff table-input-sm" value="' + (old['member-retire-coeff'] || '0.7') + '" min="0" max="2" step="0.05"></td>';
    html += '</tr>';
  });
  html += '</table>';
  container.innerHTML = html;
}

function syncInsuranceRows() {
  var container = document.getElementById('insurance-rows');
  if (!container) return;
  var members = getMembers();
  var existing = readExistingRows('#insurance-rows', 'ins-row', [
    'ins-medical',
    'ins-term-cov',
    'ins-hci-cov',
    'ins-ci-cov',
    'ins-reimb-rate',
    'ins-hc-starting',
    'ins-hc-growth',
    'ins-hc-cap'
  ]);
  var html = '<table class="form-table ins-table">';
  html += '<tr><th class="align-left">成员 / Member</th><th>医保 / Public medical</th><th>定寿保额(元) / Term life</th><th>高端医疗险保额(元) / High-end medical</th><th>重疾险保额(元) / Critical illness</th><th>报销比例 / Reimbursement</th><th>退休医疗年支出(元) / Retirement healthcare</th><th>年增长率 / Growth</th><th>年度封顶(元) / Annual cap</th></tr>';
  members.forEach(function(member, idx) {
    var old = existing[idx] || {};
    html += '<tr class="ins-row">';
    html += '<td class="align-left"><strong>' + member.name + '</strong></td>';
    html += '<td><select class="ins-medical table-input-sm"><option value="">—</option><option value="true"' + (old['ins-medical'] === 'true' ? ' selected' : '') + '>有 / Yes</option><option value="false"' + (old['ins-medical'] === 'false' ? ' selected' : '') + '>无 / No</option></select></td>';
    html += '<td><input type="number" class="ins-term-cov table-input-md" value="' + (old['ins-term-cov'] || '') + '" min="0"></td>';
    html += '<td><input type="number" class="ins-hci-cov table-input-md" value="' + (old['ins-hci-cov'] || '') + '" min="0"></td>';
    html += '<td><input type="number" class="ins-ci-cov table-input-md" value="' + (old['ins-ci-cov'] || '') + '" min="0"></td>';
    html += '<td><input type="number" class="ins-reimb-rate table-input-sm" value="' + (old['ins-reimb-rate'] || '0.8') + '" min="0" max="1" step="0.05"></td>';
    html += '<td><input type="number" class="ins-hc-starting table-input-md" value="' + (old['ins-hc-starting'] || '') + '" min="0"></td>';
    html += '<td><input type="number" class="ins-hc-growth table-input-sm" value="' + (old['ins-hc-growth'] || '0.05') + '" min="0" max="1" step="0.01"></td>';
    html += '<td><input type="number" class="ins-hc-cap table-input-md" value="' + (old['ins-hc-cap'] || '') + '" min="0"></td>';
    html += '</tr>';
  });
  html += '</table>';
  container.innerHTML = html;
}

function refreshMemberDrivenSections() {
  syncIncomeRows();
  syncExpenseRows();
  syncInsuranceRows();
  bindStaticEvents();
  updateFamilyTotals();
}

function updateFamilyTotals() {
  var totalIncome = 0;
  var totalExpense = 0;

  document.querySelectorAll('#income-rows .income-row').forEach(function(row) {
    var income = numVal(row, 'member-current-income');
    if (income !== null) totalIncome += income;
  });
  document.querySelectorAll('#expense-rows .expense-row').forEach(function(row) {
    var expense = numVal(row, 'member-expense');
    if (expense !== null) totalExpense += expense;
  });

  var householdExtra = numVal(document.getElementById('household-extra-monthly'));
  if (householdExtra !== null) totalExpense += householdExtra;

  document.querySelectorAll('#liabilities-list .dynamic-row').forEach(function(row) {
    var payment = numVal(row, 'liab-monthly');
    if (payment !== null) totalExpense += payment;
  });

  var incomeEl = document.getElementById('family-income-total');
  var expenseEl = document.getElementById('family-expense-total');
  var surplusEl = document.getElementById('family-surplus-total');
  if (incomeEl) incomeEl.textContent = '¥' + totalIncome.toLocaleString();
  if (expenseEl) expenseEl.textContent = '¥' + totalExpense.toLocaleString();
  if (surplusEl) surplusEl.textContent = '¥' + Math.round(totalIncome / 12 - totalExpense).toLocaleString();
}

function eventMaxYear() {
  var maxYear = null;
  document.querySelectorAll('#events-tbody .evt-year').forEach(function(el) {
    var year = numVal(el);
    if (year === null) return;
    if (maxYear === null || year > maxYear) maxYear = year;
  });
  return maxYear;
}

function updateMeasurementEndYearConstraints() {
  var currentYearEl = document.getElementById('current_year');
  var endYearEl = document.getElementById('measurement_end_year');
  if (!currentYearEl || !endYearEl) return;

  var currentYear = numVal(currentYearEl);
  var lastEventYear = eventMaxYear();
  var defaultYear = currentYear !== null ? currentYear + 30 : null;
  var minYear = currentYear !== null ? currentYear : 2020;
  if (lastEventYear !== null && lastEventYear > minYear) minYear = lastEventYear;
  var preferredYear = lastEventYear !== null ? lastEventYear : defaultYear;

  endYearEl.min = String(minYear);
  if (!endYearEl.value.trim() && preferredYear !== null) {
    endYearEl.value = String(Math.max(preferredYear, minYear));
  }

  var currentValue = numVal(endYearEl);
  if (currentValue === null && preferredYear !== null) {
    currentValue = preferredYear;
  }
  if (currentValue !== null && currentValue < minYear) {
    endYearEl.value = String(minYear);
  }

  if (lastEventYear !== null) {
    endYearEl.title = '不能早于重大支出规划中的最后一个年份（' + lastEventYear + '） / Cannot be earlier than the last major spending year.';
  } else {
    endYearEl.title = '默认当前年份 + 30 年，可按需要调整 / Defaults to current year + 30 and can be changed.';
  }
}

function validateMeasurementEndYear() {
  var endYearEl = document.getElementById('measurement_end_year');
  if (!endYearEl) return true;

  updateMeasurementEndYearConstraints();

  var endYear = numVal(endYearEl);
  var minYear = Number(endYearEl.min || '0');
  if (endYear === null) {
    endYearEl.setCustomValidity('请填写测算截止年份 / Please enter the projection end year.');
    return false;
  }
  if (endYear < minYear) {
    endYearEl.setCustomValidity('测算截止年份不能早于重大支出规划中的最后一个年份 / Projection end year cannot be earlier than the last major spending year.');
    return false;
  }
  endYearEl.setCustomValidity('');
  return true;
}

function collectFormData() {
  var data = {
    profile_version: '0.1',
    schema_version: 'handbook-v0.1'
  };

  var members = [];
  var baseMembers = getMembers();
  var incomeRows = document.querySelectorAll('#income-rows .income-row');
  var expenseRows = document.querySelectorAll('#expense-rows .expense-row');
  var insRows = document.querySelectorAll('#insurance-rows .ins-row');

  baseMembers.forEach(function(member, idx) {
    var m = {
      name: member.name,
      age: member.age,
      role: member.role
    };
    if (member.retirementAge !== null) m.retirement_age = member.retirementAge;

    var incomeRow = incomeRows[idx];
    if (incomeRow) {
      var currentIncome = numVal(incomeRow, 'member-current-income');
      if (currentIncome !== null) m.annual_income = currentIncome;
      var startAge = numVal(incomeRow, 'member-income-start-age');
      if (startAge !== null) m.income_start_age = startAge;
      var startAnnual = numVal(incomeRow, 'member-income-start-annual');
      if (startAnnual !== null) m.income_start_annual = startAnnual;
      var pension = numVal(incomeRow, 'member-pension');
      if (pension !== null) m.retirement_pension = pension;
      var annuity = numVal(incomeRow, 'member-annuity');
      if (annuity !== null) m.retirement_annuity = annuity;
    }

    var expenseRow = expenseRows[idx];
    if (expenseRow) {
      var monthlyExpense = numVal(expenseRow, 'member-expense');
      if (monthlyExpense !== null) m.monthly_expense = monthlyExpense;
      var retireCoeff = floatVal(expenseRow.querySelector('.member-retire-coeff'));
      if (retireCoeff !== null) m.retirement_expense_coeff = retireCoeff;
    }

    var insRow = insRows[idx];
    if (insRow) {
      var med = insRow.querySelector('.ins-medical');
      if (med && med.value === 'true') m.medical_covered = true;
      if (med && med.value === 'false') m.medical_covered = false;
      var tl = numVal(insRow, 'ins-term-cov');
      if (tl !== null && tl > 0) m.term_life_coverage = tl;
      var hci = numVal(insRow, 'ins-hci-cov');
      if (hci !== null && hci > 0) m.hci_coverage = hci;
      var ci = numVal(insRow, 'ins-ci-cov');
      if (ci !== null && ci > 0) m.critical_illness_coverage = ci;
      var rr = floatVal(insRow.querySelector('.ins-reimb-rate'));
      if (rr !== null) m.reimbursement_rate = rr;
      var hcStart = numVal(insRow, 'ins-hc-starting');
      if (hcStart !== null) m.healthcare_starting_annual = hcStart;
      var hcGrowth = floatVal(insRow.querySelector('.ins-hc-growth'));
      if (hcGrowth !== null) m.healthcare_growth_rate = hcGrowth;
      var hcCap = numVal(insRow, 'ins-hc-cap');
      if (hcCap !== null) m.healthcare_annual_cap = hcCap;
    }

    members.push(m);
  });
  data.family = { members: members };

  var totalCurrentIncome = 0;
  var totalCurrentExpense = 0;
  var totalPension = 0;
  var totalAnnuity = 0;
  members.forEach(function(member) {
    if (member.annual_income) totalCurrentIncome += member.annual_income;
    if (member.monthly_expense) totalCurrentExpense += member.monthly_expense;
    if (member.retirement_pension) totalPension += member.retirement_pension;
    if (member.retirement_annuity) totalAnnuity += member.retirement_annuity;
  });

  var householdExtraMonthly = numVal(document.getElementById('household-extra-monthly'));
  if (householdExtraMonthly !== null) totalCurrentExpense += householdExtraMonthly;

  var income = {};
  if (totalCurrentIncome > 0) income.total_annual_income = totalCurrentIncome;
  if (totalCurrentExpense > 0) income.monthly_living_expense = totalCurrentExpense;
  if (householdExtraMonthly !== null) income.household_extra_monthly_expense = householdExtraMonthly;

  var retirement = {};
  if (totalPension > 0) retirement.monthly_pension = totalPension;
  if (totalAnnuity > 0) retirement.monthly_annuity = totalAnnuity;
  if (Object.keys(retirement).length > 0) income.retirement = retirement;
  data.income = income;

  var events = [];
  document.querySelectorAll('#events-tbody .evt-row').forEach(function(row) {
    var id = val(row, 'evt-id');
    if (!id) return;
    var event = { id: id };
    var type = val(row, 'evt-type');
    if (type) event.type = type;
    var desc = val(row, 'evt-desc');
    if (desc) event.description = desc;
    var year = numVal(row, 'evt-year');
    if (year !== null) event.timing_year = year;
    var amount = numVal(row, 'evt-amount');
    if (amount !== null) event.estimated_amount = amount;
    var owner = val(row, 'evt-owner');
    if (owner) event.owner = owner;
    events.push(event);
  });
  data.events = events;

  var assets = { real_estate: {}, financial: {} };
  var primaryValue = numVal(document.getElementById('primary-value'));
  if (primaryValue !== null) assets.real_estate.primary_residence = { estimated_value: primaryValue };
  var totalFinancial = numVal(document.getElementById('financial-total-value'));
  if (totalFinancial !== null) assets.financial.total_value = totalFinancial;
  var liquidity = numVal(document.getElementById('liquidity-months'));
  if (liquidity !== null) assets.liquidity_reserve_months = liquidity;

  var savings = [];
  document.querySelectorAll('#savings-tbody .sav-row').forEach(function(row) {
    var amount = numVal(row, 'sav-amount');
    if (amount === null || amount <= 0) return;
    var item = { amount: amount };
    var premium = numVal(row, 'sav-premium');
    if (premium !== null && premium > 0) item.premium = premium;
    var payYears = numVal(row, 'sav-pay-years');
    if (payYears !== null) item.pay_years = payYears;
    var linked = val(row, 'sav-linked');
    if (linked) item.linked_account = linked;
    savings.push(item);
  });
  if (savings.length > 0) assets.financial.savings = savings;

  var liabilities = [];
  document.querySelectorAll('#liabilities-list .dynamic-row').forEach(function(row) {
    var outstanding = numVal(row, 'liab-outstanding');
    if (outstanding === null) return;
    var item = { outstanding: outstanding };
    var monthly = numVal(row, 'liab-monthly');
    if (monthly !== null) item.monthly_payment = monthly;
    var years = numVal(row, 'liab-years');
    if (years !== null) item.remaining_years = years;
    liabilities.push(item);
  });
  if (liabilities.length > 0) assets.liabilities = liabilities;
  data.assets = assets;

  var advisor = {};
  var risk = document.getElementById('risk-tolerance');
  if (risk && risk.value) advisor.risk_tolerance = risk.value;
  if (Object.keys(advisor).length > 0) data.advisor_assessment = advisor;

  var assumptions = {};
  var assetClasses = {};

  function gatherSingle(selector, key) {
    var el = document.querySelector(selector);
    if (!el) return null;
    var value = floatVal(el);
    if (value === null) return null;
    var out = {};
    out[key] = value;
    return out;
  }

  function mergeInto(obj, selector, key) {
    var partial = gatherSingle(selector, key);
    if (partial) Object.assign(obj, partial);
  }

  var fi = gatherSingle('.as-fi-ret', 'return_pct') || {};
  mergeInto(fi, '.as-fi-vol', 'volatility_pct');
  if (fi.return_pct || fi.volatility_pct) assetClasses.fixed_income = fi;

  var eq = gatherSingle('.as-eq-ret', 'return_pct') || {};
  mergeInto(eq, '.as-eq-vol', 'volatility_pct');
  if (eq.return_pct || eq.volatility_pct) assetClasses.equity = eq;

  var ins = gatherSingle('.as-ins-ret', 'return_pct') || {};
  mergeInto(ins, '.as-ins-vol', 'volatility_pct');
  if (ins.return_pct || ins.volatility_pct) assetClasses.insurance = ins;

  var alt = gatherSingle('.as-alt-ret', 'return_pct') || {};
  mergeInto(alt, '.as-alt-vol', 'volatility_pct');
  if (alt.return_pct || alt.volatility_pct) assetClasses.alternatives = alt;

  if (Object.keys(assetClasses).length > 0) assumptions.asset_classes = assetClasses;

  var corr = {};
  ['fi_eq', 'fi_ins', 'fi_alt', 'eq_ins', 'eq_alt', 'ins_alt'].forEach(function(key) {
    var el = document.querySelector('.as-corr-' + key.replace('_', '-'));
    var value = floatVal(el);
    if (value !== null) corr[key] = value;
  });
  if (Object.keys(corr).length > 0) assumptions.correlations = corr;

  var phases = [];
  for (var idx = 0; idx < 4; idx++) {
    var maxYears = numVal(document.querySelector('.as-ph-max-' + idx));
    if (maxYears === null) continue;
    var w0 = floatVal(document.querySelector('.as-ph-' + idx + '-fi'));
    var w1 = floatVal(document.querySelector('.as-ph-' + idx + '-eq'));
    var w2 = floatVal(document.querySelector('.as-ph-' + idx + '-ins'));
    var w3 = floatVal(document.querySelector('.as-ph-' + idx + '-alt'));
    if (w0 === null || w1 === null || w2 === null || w3 === null) continue;
    phases.push({ max_years: maxYears, weights: [w0, w1, w2, w3] });
  }
  if (phases.length > 0) assumptions.phases = phases;

  var projection = {};
  var retireHorizon = numVal(document.querySelector('.as-retire-horizon'));
  if (retireHorizon !== null) projection.post_retirement_horizon_years = retireHorizon;
  var measurementEndYear = numVal(document.getElementById('measurement_end_year'));
  if (measurementEndYear !== null) projection.measurement_end_year = measurementEndYear;
  if (Object.keys(projection).length > 0) assumptions.projection = projection;
  if (Object.keys(assumptions).length > 0) data.assumptions = assumptions;

  return data;
}

function fillMemberBase(data) {
  if (!data.family || !data.family.members || data.family.members.length === 0) {
    ensureExactDynamicRows('#members-list', 0);
    return;
  }
  ensureExactDynamicRows('#members-list', data.family.members.length);
  var rows = document.querySelectorAll('#members-list .dynamic-row');
  data.family.members.forEach(function(member, idx) {
    if (idx >= rows.length) return;
    setVal(rows[idx], 'member-name', member.name || '');
    setVal(rows[idx], 'member-age', member.age != null ? member.age : '');
    setVal(rows[idx], 'member-role', member.role || '');
    setVal(rows[idx], 'member-retire-age', member.retirement_age != null ? member.retirement_age : '');
  });
}

function restoreEvents(data) {
  ensureExactTableRows('#events-tbody', '.evt-row', data.events ? data.events.length : 0, addEventRow);
  if (!data.events || data.events.length === 0) {
    syncSavingsDropdown();
    return;
  }
  var rows = document.querySelectorAll('#events-tbody .evt-row');
  data.events.forEach(function(event, idx) {
    if (idx >= rows.length) return;
    setVal(rows[idx], 'evt-id', event.id || '');
    setVal(rows[idx], 'evt-type', event.type || '');
    setVal(rows[idx], 'evt-desc', event.description || '');
    setVal(rows[idx], 'evt-year', event.timing_year != null ? event.timing_year : '');
    setVal(rows[idx], 'evt-amount', event.estimated_amount != null ? event.estimated_amount : '');
    setVal(rows[idx], 'evt-owner', event.owner || '');
  });
  syncSavingsDropdown();
}

function restoreAssets(data) {
  if (!data.assets) return;
  var assets = data.assets;
  if (assets.real_estate && assets.real_estate.primary_residence && assets.real_estate.primary_residence.estimated_value != null) {
    svi('primary-value', assets.real_estate.primary_residence.estimated_value);
  }
  if (assets.financial && assets.financial.total_value != null) {
    svi('financial-total-value', assets.financial.total_value);
  }
  if (assets.liquidity_reserve_months != null) svi('liquidity-months', assets.liquidity_reserve_months);
  ensureExactDynamicRows('#liabilities-list', assets.liabilities ? assets.liabilities.length : 0);
  if (assets.liabilities && assets.liabilities.length > 0) {
    var rows = document.querySelectorAll('#liabilities-list .dynamic-row');
    assets.liabilities.forEach(function(item, idx) {
      if (idx >= rows.length) return;
      setVal(rows[idx], 'liab-outstanding', item.outstanding != null ? item.outstanding : '');
      setVal(rows[idx], 'liab-monthly', item.monthly_payment != null ? item.monthly_payment : '');
      setVal(rows[idx], 'liab-years', item.remaining_years != null ? item.remaining_years : '');
    });
  }
  ensureExactTableRows('#savings-tbody', '.sav-row', assets.financial && assets.financial.savings ? assets.financial.savings.length : 0, addSavingsRow);
  if (assets.financial && assets.financial.savings) {
    var sRows = document.querySelectorAll('#savings-tbody .sav-row');
    assets.financial.savings.forEach(function(item, idx) {
      if (idx >= sRows.length) return;
      setVal(sRows[idx], 'sav-amount', item.amount != null ? item.amount : '');
      setVal(sRows[idx], 'sav-premium', item.premium != null ? item.premium : '');
      setVal(sRows[idx], 'sav-pay-years', item.pay_years != null ? item.pay_years : '');
      setVal(sRows[idx], 'sav-linked', item.linked_account || '');
    });
  }
}

function restoreAssumptions(data) {
  if (!data.assumptions) return;
  var assumptions = data.assumptions;
  if (assumptions.asset_classes) {
    var ac = assumptions.asset_classes;
    if (ac.fixed_income) {
      if (ac.fixed_income.return_pct != null) sviByClass('as-fi-ret', ac.fixed_income.return_pct);
      if (ac.fixed_income.volatility_pct != null) sviByClass('as-fi-vol', ac.fixed_income.volatility_pct);
    }
    if (ac.equity) {
      if (ac.equity.return_pct != null) sviByClass('as-eq-ret', ac.equity.return_pct);
      if (ac.equity.volatility_pct != null) sviByClass('as-eq-vol', ac.equity.volatility_pct);
    }
    if (ac.insurance) {
      if (ac.insurance.return_pct != null) sviByClass('as-ins-ret', ac.insurance.return_pct);
      if (ac.insurance.volatility_pct != null) sviByClass('as-ins-vol', ac.insurance.volatility_pct);
    }
    if (ac.alternatives) {
      if (ac.alternatives.return_pct != null) sviByClass('as-alt-ret', ac.alternatives.return_pct);
      if (ac.alternatives.volatility_pct != null) sviByClass('as-alt-vol', ac.alternatives.volatility_pct);
    }
  }
  if (assumptions.correlations) {
    Object.keys(assumptions.correlations).forEach(function(key) {
      sviByClass('as-corr-' + key.replace('_', '-'), assumptions.correlations[key]);
    });
  }
  if (assumptions.phases) {
    assumptions.phases.forEach(function(phase, idx) {
      if (idx >= 4) return;
      sviByClass('as-ph-max-' + idx, phase.max_years);
      if (phase.weights && phase.weights.length === 4) {
        sviByClass('as-ph-' + idx + '-fi', phase.weights[0]);
        sviByClass('as-ph-' + idx + '-eq', phase.weights[1]);
        sviByClass('as-ph-' + idx + '-ins', phase.weights[2]);
        sviByClass('as-ph-' + idx + '-alt', phase.weights[3]);
      }
    });
    var riskEl = document.getElementById('risk-tolerance');
    _phaseWeightsManuallyEdited = !(riskEl && riskEl.value && currentPhaseMatchesTemplate(riskEl.value));
  }
  if (assumptions.projection && assumptions.projection.post_retirement_horizon_years != null) {
    sviByClass('as-retire-horizon', assumptions.projection.post_retirement_horizon_years);
  }
  if (assumptions.projection && assumptions.projection.measurement_end_year != null) {
    svi('measurement_end_year', assumptions.projection.measurement_end_year);
  }
}

function restoreMemberDrivenData(data) {
  var members = data.family && data.family.members ? data.family.members : [];
  if (members.length === 0) return;
  var incomeRows = document.querySelectorAll('#income-rows .income-row');
  var expenseRows = document.querySelectorAll('#expense-rows .expense-row');
  var insRows = document.querySelectorAll('#insurance-rows .ins-row');

  members.forEach(function(member, idx) {
    if (incomeRows[idx]) {
      if (member.annual_income != null) setVal(incomeRows[idx], 'member-current-income', member.annual_income);
      if (member.income_start_age != null) setVal(incomeRows[idx], 'member-income-start-age', member.income_start_age);
      if (member.income_start_annual != null) setVal(incomeRows[idx], 'member-income-start-annual', member.income_start_annual);
      if (member.retirement_pension != null) setVal(incomeRows[idx], 'member-pension', member.retirement_pension);
      if (member.retirement_annuity != null) setVal(incomeRows[idx], 'member-annuity', member.retirement_annuity);
    }
    if (expenseRows[idx]) {
      if (member.monthly_expense != null) setVal(expenseRows[idx], 'member-expense', member.monthly_expense);
      if (member.retirement_expense_coeff != null) setVal(expenseRows[idx], 'member-retire-coeff', member.retirement_expense_coeff);
    }
    if (insRows[idx]) {
      if (member.medical_covered === true) setVal(insRows[idx], 'ins-medical', 'true');
      if (member.medical_covered === false) setVal(insRows[idx], 'ins-medical', 'false');
      if (member.term_life_coverage != null) setVal(insRows[idx], 'ins-term-cov', member.term_life_coverage);
      if (member.hci_coverage != null) setVal(insRows[idx], 'ins-hci-cov', member.hci_coverage);
      if (member.critical_illness_coverage != null) setVal(insRows[idx], 'ins-ci-cov', member.critical_illness_coverage);
      if (member.reimbursement_rate != null) setVal(insRows[idx], 'ins-reimb-rate', member.reimbursement_rate);
      if (member.healthcare_starting_annual != null) setVal(insRows[idx], 'ins-hc-starting', member.healthcare_starting_annual);
      if (member.healthcare_growth_rate != null) setVal(insRows[idx], 'ins-hc-growth', member.healthcare_growth_rate);
      if (member.healthcare_annual_cap != null) setVal(insRows[idx], 'ins-hc-cap', member.healthcare_annual_cap);
    }
  });
}

function restoreIncomeFallbacks(data) {
  if (!data.income) return;
  var firstIncomeRow = document.querySelector('#income-rows .income-row');
  var firstExpenseRow = document.querySelector('#expense-rows .expense-row');
  if (firstIncomeRow) {
    if (numVal(firstIncomeRow, 'member-current-income') === null && data.income.total_annual_income) {
      setVal(firstIncomeRow, 'member-current-income', data.income.total_annual_income);
    }
  }
  if (firstExpenseRow) {
    if (numVal(firstExpenseRow, 'member-expense') === null && data.income.monthly_living_expense) {
      setVal(firstExpenseRow, 'member-expense', data.income.monthly_living_expense);
    }
  }

  if (data.income.household_extra_monthly_expense != null) {
    svi('household-extra-monthly', data.income.household_extra_monthly_expense);
  }

}

function restoreFormFromData(data) {
  fillMemberBase(data);
  refreshMemberDrivenSections();
  restoreMemberDrivenData(data);
  restoreIncomeFallbacks(data);
  restoreEvents(data);
  restoreAssets(data);

  if (data.advisor_assessment && data.advisor_assessment.risk_tolerance) {
    svi('risk-tolerance', data.advisor_assessment.risk_tolerance);
  }
  restoreAssumptions(data);
  var riskEl = document.getElementById('risk-tolerance');
  if (riskEl && riskEl.value && (!data.assumptions || !data.assumptions.phases)) {
    applyRiskTemplate(riskEl.value, { preserveManualFlag: false });
  } else {
    updatePhaseSyncStatus();
  }
  updateMeasurementEndYearConstraints();
  syncSavingsDropdown();
  updateFamilyTotals();
}

function tryRestoreForm() {
  var raw;
  try {
    raw = sessionStorage.getItem('fapm_form_data');
  } catch (err) {
    return;
  }
  if (!raw) return;

  var data;
  try {
    data = JSON.parse(raw);
  } catch (err) {
    return;
  }

  if (!document.querySelector('.error-banner')) {
    try { sessionStorage.removeItem('fapm_form_data'); } catch (err2) {}
    return;
  }

  restoreFormFromData(data);
  try { sessionStorage.removeItem('fapm_form_data'); } catch (err3) {}
}

function autoPrefillSample() {
  var el = document.getElementById('sample-data');
  if (!el || !el.textContent || el.textContent === '{}') return;
  if (!window.__forcePrefill && document.querySelector('.error-banner')) return;
  try {
    var data = JSON.parse(el.textContent);
    if (data && Object.keys(data).length > 0) restoreFormFromData(data);
  } catch (err) {
    console.warn('prefill error', err);
  }
}

function loadSampleData() {
  var el = document.getElementById('sample-data');
  if (!el || !el.textContent) {
    alert('无示例数据 / No sample data');
    return;
  }
  try {
    var data = JSON.parse(el.textContent);
    if (data && Object.keys(data).length > 0) restoreFormFromData(data);
  } catch (err) {
    alert('解析示例数据失败 / Failed to parse sample data');
  }
}

function bindStaticEvents() {
  document.querySelectorAll('#members-list .member-name, #members-list .member-age, #members-list .member-role, #members-list .member-retire-age').forEach(function(el) {
    if (el.dataset.boundMember === '1') return;
    el.dataset.boundMember = '1';
    el.addEventListener('input', refreshMemberDrivenSections);
    el.addEventListener('change', refreshMemberDrivenSections);
  });

  document.querySelectorAll('#income-rows .member-current-income, #expense-rows .member-expense, #liabilities-list .liab-monthly, #household-extra-monthly').forEach(function(el) {
    if (el.dataset.boundSummary === '1') return;
    el.dataset.boundSummary = '1';
    el.addEventListener('input', updateFamilyTotals);
    el.addEventListener('change', updateFamilyTotals);
  });

  document.querySelectorAll('#events-tbody .evt-type').forEach(function(el) {
    if (el.dataset.boundEventType === '1') return;
    el.dataset.boundEventType = '1';
    el.addEventListener('change', function() {
      autoGenEventId(el);
      syncSavingsDropdown();
    });
  });
  document.querySelectorAll('#events-tbody .evt-desc, #events-tbody .evt-year, #events-tbody .evt-id').forEach(function(el) {
    if (el.dataset.boundEventMeta === '1') return;
    el.dataset.boundEventMeta = '1';
    el.addEventListener('input', syncSavingsDropdown);
    el.addEventListener('change', syncSavingsDropdown);
    if (el.classList.contains('evt-year')) {
      el.addEventListener('input', updateMeasurementEndYearConstraints);
      el.addEventListener('change', updateMeasurementEndYearConstraints);
    }
  });

  var riskEl = document.getElementById('risk-tolerance');
  if (riskEl && riskEl.dataset.boundRiskTemplate !== '1') {
    riskEl.dataset.boundRiskTemplate = '1';
    riskEl.addEventListener('change', syncRiskToPhasesIfAllowed);
    riskEl.addEventListener('input', syncRiskToPhasesIfAllowed);
  }

  document.querySelectorAll(
    '.as-ph-max-0, .as-ph-max-1, .as-ph-max-2, .as-ph-max-3,' +
    ' .as-ph-0-fi, .as-ph-0-eq, .as-ph-0-ins, .as-ph-0-alt,' +
    ' .as-ph-1-fi, .as-ph-1-eq, .as-ph-1-ins, .as-ph-1-alt,' +
    ' .as-ph-2-fi, .as-ph-2-eq, .as-ph-2-ins, .as-ph-2-alt,' +
    ' .as-ph-3-fi, .as-ph-3-eq, .as-ph-3-ins, .as-ph-3-alt'
  ).forEach(function(el) {
    if (el.dataset.boundPhaseEdit === '1') return;
    el.dataset.boundPhaseEdit = '1';
    el.addEventListener('input', markPhaseWeightsEdited);
    el.addEventListener('change', markPhaseWeightsEdited);
  });

  var resetBtn = document.getElementById('phase-reset-btn');
  if (resetBtn && resetBtn.dataset.boundPhaseReset !== '1') {
    resetBtn.dataset.boundPhaseReset = '1';
    resetBtn.addEventListener('click', function() {
      var risk = document.getElementById('risk-tolerance');
      if (!risk || !risk.value) return;
      applyRiskTemplate(risk.value);
    });
  }
}

document.addEventListener('DOMContentLoaded', function() {
  var form = document.getElementById('questionnaire-form');
  if (!form) return;

  form.addEventListener('submit', function(event) {
    if (!validateMeasurementEndYear()) {
      var endYearEl = document.getElementById('measurement_end_year');
      if (endYearEl) endYearEl.reportValidity();
      event.preventDefault();
      return;
    }
    var data = collectFormData();
    document.getElementById('yaml_content').value = toYAML(data, 0);
    try {
      sessionStorage.setItem('fapm_form_data', JSON.stringify(data));
      var code = document.getElementById('client_code');
      if (code) sessionStorage.setItem('fapm_client_code', code.value);
    } catch (err) {}
  });

  renderRiskTemplateSummaries();
  bindStaticEvents();
  refreshMemberDrivenSections();
  tryRestoreForm();
  autoPrefillSample();
  bindStaticEvents();
  if (!document.getElementById('sample-data') || document.getElementById('sample-data').textContent === '{}') {
    syncRiskToPhasesIfAllowed();
  } else {
    updatePhaseSyncStatus();
  }
  updateMeasurementEndYearConstraints();
  syncSavingsDropdown();
  updateFamilyTotals();

  var currentYearEl = document.getElementById('current_year');
  var endYearEl = document.getElementById('measurement_end_year');
  if (currentYearEl && currentYearEl.dataset.boundMeasurement !== '1') {
    currentYearEl.dataset.boundMeasurement = '1';
    currentYearEl.addEventListener('input', updateMeasurementEndYearConstraints);
    currentYearEl.addEventListener('change', updateMeasurementEndYearConstraints);
  }
  if (endYearEl && endYearEl.dataset.boundMeasurement !== '1') {
    endYearEl.dataset.boundMeasurement = '1';
    endYearEl.addEventListener('input', validateMeasurementEndYear);
    endYearEl.addEventListener('change', validateMeasurementEndYear);
  }

  document.querySelectorAll('#events-tbody .evt-type').forEach(function(sel) {
    if (sel.value) {
      _eventSeq[sel.value] = (_eventSeq[sel.value] || 0) + 1;
    }
  });
});
