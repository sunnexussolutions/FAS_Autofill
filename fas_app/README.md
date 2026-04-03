# FAS Form Auto-Filler v2.0
## Sandip University, Nashik

---

## Folder Structure

```
fas_app/
├── app.py              ← Python server (run this)
├── README.md           ← This file
├── data/
│   └── coordinator.json  ← Auto-created when coordinator saves details
└── static/
    ├── index.html      ← Main web page
    ├── style.css       ← All styles
    └── app.js          ← All frontend logic
```

---

## How to Run

```bash
python app.py
```

Browser opens automatically at **http://localhost:8765**

---

## How It Works

### Tab 1 — Generate Forms
1. Upload your **student Excel sheet** (.xlsx)
2. Upload the **blank FAS form PDF**
3. Type a student **PRN number** → their details are fetched
4. Click **Generate & Download** → filled PDF saves to your device

### Tab 2 — Coordinator Profile
1. Enter all coordinator/mentor details
2. Click **Save Coordinator Details**
3. A green badge appears in the navbar — coordinator is now active
4. Every FAS form generated will automatically include coordinator
   details in the **Mentor Information page** (both tables)

### Changing Coordinator
1. Go to **Coordinator Profile** tab
2. Click **Unsave & Change**
3. Enter new coordinator details
4. Click **Save** → new coordinator applied to all future forms

---

## What Gets Filled

| Page              | Fields Filled                                        |
|-------------------|------------------------------------------------------|
| Cover             | Name, School, Department, Programme, PRN, Year       |
| Mentor Info       | Name, School, Dept, Contact, Email, Mentees, Class   |
| Student Details   | All 9 table rows, addresses, parent mobiles, guardian|
| Educational       | 10th/12th/Diploma, family, hobbies, activities       |
| Academic Progress | Sem 1–8 CGPA/Grade/Remarks, Consolidated, Date, Sign |

---

## Requirements

Python 3.8+ with these packages (auto-installed on first run):
- pypdf
- reportlab
- pandas
- openpyxl

---

## Notes

- Coordinator profile is saved in `data/coordinator.json` — persists
  across server restarts until you unsave it
- No internet required — everything runs locally on your machine
- Works with any number of students in the Excel file
