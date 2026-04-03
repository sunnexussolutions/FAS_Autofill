/* ============================================================
   FAS Form Auto-Filler — app.js
   All UI logic split cleanly from server (app.py)
   ============================================================ */

/* ── State ──────────────────────────────────────────────────── */
let excelReady = false;
let pdfReady   = false;
let currentPRN = '';
let currentName = '';
let previewVisible = false;

/* ── Tab switching ───────────────────────────────────────────── */
function switchTab(name) {
  document.getElementById('pane-generate').style.display     = name === 'generate'     ? 'block' : 'none';
  document.getElementById('pane-coordinator').style.display  = name === 'coordinator'  ? 'block' : 'none';
  document.getElementById('tab-generate').className    = 'tab' + (name === 'generate'    ? ' active' : '');
  document.getElementById('tab-coordinator').className = 'tab' + (name === 'coordinator' ? ' active' : '');
}

/* ── Alert helpers ───────────────────────────────────────────── */
function showAlert(id, type, html) {
  const el = document.getElementById(id);
  el.className = `alert alert-${type} show`;
  el.innerHTML = html;
}
function hideAlert(id) {
  const el = document.getElementById(id);
  el.className = 'alert';
  el.innerHTML = '';
}

/* ── Step tracker ────────────────────────────────────────────── */
function setStep(n) {
  for (let i = 1; i <= 4; i++) {
    const circle = document.getElementById('sc' + i);
    const label  = document.getElementById('sl' + i);
    const line   = document.getElementById('sn' + i);
    if (i < n) {
      circle.className = 'step-circle done'; circle.textContent = '✓';
      label.className  = 'step-label done';
      if (line) line.className = 'step-line done';
    } else if (i === n) {
      circle.className = 'step-circle active'; circle.textContent = i;
      label.className  = 'step-label active';
      if (line) line.className = 'step-line done';
    } else {
      circle.className = 'step-circle'; circle.textContent = i;
      label.className  = 'step-label';
      if (line) line.className = 'step-line';
    }
  }
}

/* ── Drag & drop ─────────────────────────────────────────────── */
function bindDropZone(zoneId, fileId, handler) {
  const zone = document.getElementById(zoneId);
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag');
    if (e.dataTransfer.files[0]) handler(e.dataTransfer.files[0]);
  });
  document.getElementById(fileId).addEventListener('change', e => {
    if (e.target.files[0]) handler(e.target.files[0]);
  });
}
bindDropZone('excelZone', 'excelFile', uploadExcel);
bindDropZone('pdfZone',   'pdfFile',   uploadPDF);

/* ── POST multipart upload ───────────────────────────────────── */
function postFile(file, type, callback) {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('type', type);
  fetch('/api/upload', { method: 'POST', body: fd })
    .then(async r => {
      const text = await r.text();
      let data = null;

      if (text) {
        try {
          data = JSON.parse(text);
        } catch (_) {
          const snippet = text.replace(/\s+/g, ' ').trim().slice(0, 160);
          throw new Error(`Upload failed (HTTP ${r.status}). ${snippet || 'Non-JSON response from server.'}`);
        }
      }

      if (!r.ok) {
        throw new Error((data && data.error) || `Upload failed (HTTP ${r.status}).`);
      }
      if (!data) {
        throw new Error('Upload failed: empty server response.');
      }

      callback(data);
    })
    .catch(e => callback({ ok: false, error: e.message || String(e) }));
}

/* ── Excel upload ────────────────────────────────────────────── */
function uploadExcel(file) {
  showAlert('excelAlert', 'info', '⏳ Reading Excel file...');
  postFile(file, 'excel', d => {
    if (d.ok) {
      document.getElementById('excelZone').classList.add('done');
      const fn = document.getElementById('excelFilename');
      fn.innerHTML = '✔ ' + file.name; fn.style.display = 'flex';
      showAlert('excelAlert', 'ok',
        `✅ <strong>${d.count} student${d.count > 1 ? 's' : ''} loaded</strong> · ` +
        `${d.cols} columns · PRN column: <em>"${d.prn_col}"</em><br>` +
        `<span style="opacity:.8">Sample PRNs: ${d.sample}</span>`);
      document.getElementById('prnHint').textContent =
        `PRNs in file: ${d.sample}${d.count > 5 ? '…' : ''} — enter any PRN below`;
      excelReady = true; setStep(1); checkBothReady();
    } else {
      showAlert('excelAlert', 'err', '❌ ' + d.error);
    }
  });
}

/* ── PDF upload ──────────────────────────────────────────────── */
function uploadPDF(file) {
  showAlert('pdfAlert', 'info', '⏳ Loading FAS PDF...');
  postFile(file, 'pdf', d => {
    if (d.ok) {
      document.getElementById('pdfZone').classList.add('done');
      const fn = document.getElementById('pdfFilename');
      fn.innerHTML = '✔ ' + file.name; fn.style.display = 'flex';
      showAlert('pdfAlert', 'ok',
        `✅ FAS form loaded · ${d.pages} pages · Ready to fill`);
      pdfReady = true; setStep(2); checkBothReady();
    } else {
      showAlert('pdfAlert', 'err', '❌ ' + d.error);
    }
  });
}

/* ── Show PRN card once both files are uploaded ──────────────── */
function checkBothReady() {
  if (!excelReady || !pdfReady) return;
  const card = document.getElementById('prnCard');
  card.style.display = 'block';
  setTimeout(() => card.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 80);
  setStep(3);
  document.getElementById('prnInput').focus();
}

/* ── Find student by PRN ──────────────────────────────────────── */
function findStudent() {
  const prn = document.getElementById('prnInput').value.trim();
  if (!prn) { showAlert('prnAlert', 'err', '❌ Please enter a PRN number.'); return; }

  const btn = document.getElementById('findBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Searching...';
  showAlert('prnAlert', 'info', `🔍 Looking up PRN <strong>${prn}</strong>...`);

  fetch('/api/lookup?prn=' + encodeURIComponent(prn))
    .then(r => r.json())
    .then(d => {
      btn.disabled = false; btn.innerHTML = '🔍 Find Student';
      if (d.ok) {
        showAlert('prnAlert', 'ok', `✅ Found: <strong>${d.name}</strong>`);
        currentPRN  = prn;
        currentName = d.name || prn;
        renderPreview(d);
        setStep(3);
      } else {
        showAlert('prnAlert', 'err', '❌ ' + d.error);
        document.getElementById('previewSection').style.display  = 'none';
        document.getElementById('downloadSection').style.display = 'none';
      }
    })
    .catch(e => {
      btn.disabled = false; btn.innerHTML = '🔍 Find Student';
      showAlert('prnAlert', 'err', '❌ Network error: ' + e);
    });
}

/* ── Field labels ─────────────────────────────────────────────── */
const FIELD_LABELS = {
  prn:'PRN', student_name:'Student Name', SchoolName:'School Name',
  DepartmentName:'Department', Programme:'Programme', Yearofadmission:'Year of Admission',
  dob:'Date of Birth', mobile_number:'Mobile Number', HostelerDayScholar:'Hosteler / Day Scholar',
  PostalAddress:'Postal Address', PermanentAddress:'Permanent Address',
  PermanentPincode:'Permanent Pincode', PresentAddress:'Present Address',
  PresentPincode:'Present Pincode', FatherName:'Father Name', FatherAge:'Father Age',
  FatherQualificationOccupation:'Father Occupation', MotherName:'Mother Name',
  MotherAge:'Mother Age', MotherQualificationOccupation:'Mother Occupation',
  MotherMobileNumber1:'Mother Mobile 1', FatherMobileNumber1:'Father Mobile 1',
  MotherMobileNumber2:'Mother Mobile 2', FatherMobileNumber2:'Father Mobile 2',
  GuardianName:'Guardian Name', GuardianAddress:'Guardian Address',
  GuardianMobile:'Guardian Mobile', Sibling1Name:'Sibling 1 Name',
  Sibling1Age:'Sibling 1 Age', Sibling1QualificationOccupation:'Sibling 1 Occupation',
  Sibling2Name:'Sibling 2 Name', Sibling2Age:'Sibling 2 Age',
  Sibling2QualificationOccupation:'Sibling 2 Occupation',
  SSCBoard:'10th Board', SSCYear:'10th Year', SSCPercentage:'10th %',
  HSCBoard:'12th Board', HSCYear:'12th Year', HSCPercentage:'12th %',
  DiplomaCollege:'Diploma College', DiplomaYear:'Diploma Year', DiplomaPercentage:'Diploma %',
  HobbiesInterest:'Hobbies & Interests', CoCurricularActivities:'Co-curricular Activities',
  Achievements:'Achievements',
  Sem1CGPA:'Sem 1 CGPA', Sem1Grade:'Sem 1 Grade', Sem1Remarks:'Sem 1 Remarks',
  Sem2CGPA:'Sem 2 CGPA', Sem2Grade:'Sem 2 Grade', Sem2Remarks:'Sem 2 Remarks',
  Sem3CGPA:'Sem 3 CGPA', Sem3Grade:'Sem 3 Grade', Sem3Remarks:'Sem 3 Remarks',
  Sem4CGPA:'Sem 4 CGPA', Sem4Grade:'Sem 4 Grade', Sem4Remarks:'Sem 4 Remarks',
  Sem5CGPA:'Sem 5 CGPA', Sem5Grade:'Sem 5 Grade', Sem5Remarks:'Sem 5 Remarks',
  Sem6CGPA:'Sem 6 CGPA', Sem6Grade:'Sem 6 Grade', Sem6Remarks:'Sem 6 Remarks',
  Sem7CGPA:'Sem 7 CGPA', Sem7Grade:'Sem 7 Grade', Sem7Remarks:'Sem 7 Remarks',
  Sem8CGPA:'Sem 8 CGPA', Sem8Grade:'Sem 8 Grade', Sem8Remarks:'Sem 8 Remarks',
  ConsolidatedCGPA:'Consolidated CGPA',
};
const PRIORITY_KEYS = [
  'prn','student_name','SchoolName','DepartmentName','Programme','Yearofadmission',
  'dob','mobile_number','HostelerDayScholar','PermanentAddress','PresentAddress',
  'FatherName','MotherName','MotherMobileNumber1','FatherMobileNumber1',
  'SSCBoard','SSCPercentage','HSCBoard','HSCPercentage',
  'HobbiesInterest','CoCurricularActivities','Achievements',
  'Sem1CGPA','Sem2CGPA','Sem3CGPA','Sem4CGPA','ConsolidatedCGPA',
];

/* ── Render student preview ───────────────────────────────────── */
function renderPreview(d) {
  const { data, name, dept, programme, prn } = d;

  const initials = (name || '?').split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();
  document.getElementById('studentAvatar').textContent = initials;
  document.getElementById('studentName').textContent   = name || '—';
  document.getElementById('studentMeta').textContent   =
    [dept, programme].filter(Boolean).join(' · ') || '—';
  document.getElementById('studentPrn').textContent    = prn;

  // Check coordinator saved
  fetch('/api/coordinator')
    .then(r => r.json())
    .then(cd => {
      const note = document.getElementById('coordNote');
      const txt  = document.getElementById('coordNoteText');
      if (cd.data && cd.data.mentorName) {
        note.style.display = 'flex';
        txt.textContent = `Coordinator "${cd.data.mentorName}" details will be added to the Mentor Information page`;
      } else {
        note.style.display = 'none';
      }
    })
    .catch(() => {});

  const grid    = document.getElementById('fieldsGrid');
  grid.innerHTML = '';
  const allKeys  = Object.keys(data);
  const ordered  = [
    ...PRIORITY_KEYS.filter(k => allKeys.includes(k)),
    ...allKeys.filter(k => !PRIORITY_KEYS.includes(k)),
  ];
  ordered.forEach(k => {
    const val = String(data[k] || '');
    if (!val || val === 'nan') return;
    const chip = document.createElement('div');
    chip.className = 'field-chip';
    chip.innerHTML =
      `<div class="chip-key">${FIELD_LABELS[k] || k}</div>` +
      `<div class="chip-val" title="${val}">${val}</div>`;
    grid.appendChild(chip);
  });

  const section = document.getElementById('previewSection');
  section.style.display = 'block';
  hideAlert('generateAlert');
  document.getElementById('downloadSection').style.display = 'none';
  setTimeout(() => section.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 80);
}

/* ── Generate filled PDF ─────────────────────────────────────── */
function generateForm() {
  const btn = document.getElementById('generateBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Filling form...';
  showAlert('generateAlert', 'info', '⏳ Filling all fields at exact coordinates...');

  fetch('/api/generate?prn=' + encodeURIComponent(currentPRN))
    .then(r => {
      if (!r.ok) return r.json().then(d => Promise.reject(d.error || 'Server error'));
      return r.blob();
    })
    .then(blob => {
      const url   = URL.createObjectURL(blob);
      const alink = document.getElementById('downloadLink');
      alink.href     = url;
      alink.download = `FAS_${currentName.replace(/\s+/g, '_')}.pdf`;

      document.getElementById('dlSubtitle').innerHTML =
        `<strong>${currentName}</strong> (PRN: <strong>${currentPRN}</strong>) — ` +
        `all details filled at exact coordinates across all pages. ` +
        `Click below to save the PDF to your device.`;

      const dlSec = document.getElementById('downloadSection');
      dlSec.style.display = 'block';
      setTimeout(() => dlSec.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 80);
      showAlert('generateAlert', 'ok', '✅ PDF generated! Scroll down to download.');
      setStep(4);
      alink.click();   // auto-trigger download
    })
    .catch(e => showAlert('generateAlert', 'err', '❌ ' + e))
    .finally(() => {
      btn.disabled = false;
      btn.innerHTML = '⚡ Generate &amp; Download Filled FAS Form';
    });
}

/* ── Reset helpers ───────────────────────────────────────────── */
function resetPRN() {
  document.getElementById('prnInput').value = '';
  hideAlert('prnAlert'); hideAlert('generateAlert');
  document.getElementById('previewSection').style.display  = 'none';
  document.getElementById('downloadSection').style.display = 'none';
  currentPRN = ''; currentName = '';
  setStep(3);
  document.getElementById('prnInput').focus();
  document.getElementById('prnCard').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function fillAnother() {
  resetPRN();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && document.activeElement.id === 'prnInput') findStudent();
});


/* ============================================================
   COORDINATOR SECTION
   ============================================================ */

/* ── Load coordinator status on page load ────────────────────── */
function loadCoordinatorStatus() {
  fetch('/api/coordinator')
    .then(r => r.json())
    .then(d => {
      if (d.data && d.data.mentorName) {
        showCoordinatorSaved(d.data);
      } else {
        showCoordinatorForm();
      }
    })
    .catch(() => showCoordinatorForm());
}

/* ── Show saved state ────────────────────────────────────────── */
function showCoordinatorSaved(coord) {
  document.getElementById('savedBanner').style.display  = 'flex';
  document.getElementById('coordinatorForm').style.display = 'none';

  document.getElementById('savedName').textContent = coord.mentorName || '';
  document.getElementById('savedMeta').textContent =
    [coord.mentorSchool, coord.mentorDept, coord.mentorEmail]
      .filter(Boolean).join(' · ');

  // Update navbar badge
  const badge = document.getElementById('coordBadge');
  badge.className = 'coord-badge saved';
  document.getElementById('coordBadgeText').textContent = coord.mentorName;
  document.getElementById('coordDot').style.background  = 'var(--green)';
}

/* ── Show entry form ─────────────────────────────────────────── */
function showCoordinatorForm() {
  document.getElementById('savedBanner').style.display    = 'none';
  document.getElementById('coordinatorForm').style.display = 'block';

  // Update navbar badge
  const badge = document.getElementById('coordBadge');
  badge.className = 'coord-badge unsaved';
  document.getElementById('coordBadgeText').textContent = 'No Coordinator Saved';
  document.getElementById('coordDot').style.background  = 'var(--amber)';
}

/* ── Save coordinator ────────────────────────────────────────── */
function saveCoordinator() {
  const data = {
    mentorName:     document.getElementById('cName').value.trim(),
    mentorSchool:   document.getElementById('cSchool').value.trim(),
    mentorDept:     document.getElementById('cDept').value.trim(),
    mentorContact:  document.getElementById('cContact').value.trim(),
    mentorEmail:    document.getElementById('cEmail').value.trim(),
    mentorNoMentee: document.getElementById('cNoMentee').value.trim(),
    mentorClass:    document.getElementById('cClass').value.trim(),
  };

  if (!data.mentorName) {
    showAlert('coordAlert', 'err', '❌ Mentor Name is required.');
    return;
  }

  fetch('/api/coordinator/save', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(data),
  })
    .then(r => r.json())
    .then(d => {
      if (d.ok) {
        showCoordinatorSaved(data);
        showAlert('coordAlert', 'ok',
          '✅ Coordinator details saved! They will be automatically added to the ' +
          'Mentor Information page of every FAS form generated from now on.');
      } else {
        showAlert('coordAlert', 'err', '❌ ' + d.error);
      }
    })
    .catch(e => showAlert('coordAlert', 'err', '❌ ' + e));
}

/* ── Clear / unsave coordinator ──────────────────────────────── */
function clearCoordinator() {
  if (!confirm(
    'Are you sure you want to unsave the current coordinator?\n\n' +
    'Forms generated after this will NOT include coordinator details ' +
    'until you save a new profile.'
  )) return;

  fetch('/api/coordinator/clear', { method: 'POST' })
    .then(r => r.json())
    .then(d => {
      if (d.ok) {
        showCoordinatorForm();
        clearCoordinatorForm();
        showAlert('coordAlert', 'info',
          'ℹ️ Coordinator profile cleared. Enter new details and save when ready.');
      }
    })
    .catch(e => showAlert('coordAlert', 'err', '❌ ' + e));
}

/* ── Clear form fields ───────────────────────────────────────── */
function clearCoordinatorForm() {
  ['cName','cSchool','cDept','cContact','cEmail','cNoMentee','cClass']
    .forEach(id => { document.getElementById(id).value = ''; });
  hideAlert('coordAlert');
  document.getElementById('previewTable').style.display = 'none';
  previewVisible = false;
}

/* ── Toggle live preview table ───────────────────────────────── */
function togglePreview() {
  previewVisible = !previewVisible;
  const tbl = document.getElementById('previewTable');
  if (previewVisible) {
    updatePreviewTable();
    tbl.style.display = 'block';
  } else {
    tbl.style.display = 'none';
  }
}

function updatePreviewTable() {
  const map = {
    'pv-name':    'cName',
    'pv-school':  'cSchool',
    'pv-dept':    'cDept',
    'pv-contact': 'cContact',
    'pv-email':   'cEmail',
    'pv-nmentee': 'cNoMentee',
    'pv-class':   'cClass',
  };
  Object.entries(map).forEach(([pvId, inputId]) => {
    const val = document.getElementById(inputId).value.trim();
    const el  = document.getElementById(pvId);
    el.textContent = val || '—';
    el.style.color = val ? 'var(--blue)' : 'var(--t4)';
  });
}

// Live-update preview while typing
['cName','cSchool','cDept','cContact','cEmail','cNoMentee','cClass'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('input', () => { if (previewVisible) updatePreviewTable(); });
});

/* ── Init ────────────────────────────────────────────────────── */
loadCoordinatorStatus();
