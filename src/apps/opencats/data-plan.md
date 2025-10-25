# OpenCATS API payloads for data seeding

This document focuses on POST request payloads and minimal schemas for the core entities you asked to seed: job orders, companies, candidates, contacts, events (calendar), lists, and reports (read-only parameters). It’s distilled from the application handlers and database schema.

Notes

- Unless otherwise noted, forms post as application/x-www-form-urlencoded.
- **CRITICAL**: All form submissions MUST include `postback=postback` hidden field, or the request will only display the form page instead of processing the submission.
- Extra fields: many entities support custom "extra fields" stored separately; these are updated after insert using the entity's ExtraFields helper. Include them as additional POST fields if configured in your instance.

## Companies

Endpoint

- POST /index.php?m=companies&a=add

Payload (from modules/companies/CompaniesUI.php::onAdd)

- Required: postback (always "postback"), name
- Optional: address, city, state, zip, phone1, phone2, faxNumber, url, keyTechnologies, notes, isHot (checkbox), departmentsCSV (CSV of department names)

Validation/notes

- Phone numbers are normalized where possible.
- url is normalized if parseable.

Schema essentials (table company)

- company_id PK
- name (varchar, not null)
- address, city, state, zip
- phone1, phone2, fax_number
- url, key_technologies, notes
- entered_by, owner, date_created, date_modified
- is_hot (0/1), default_company (0/1)

Example payload
postback=postback&name=Contoso LLC&address=1 Main St&city=Austin&state=TX&zip=78701&phone1=5125550100&url=https://contoso.example&isHot=1&keyTechnologies=PHP, MySQL&notes=Preferred client

JSON equivalent
{
"postback": "postback",
"name": "Contoso LLC",
"address": "1 Main St",
"city": "Austin",
"state": "TX",
"zip": "78701",
"phone1": "5125550100",
"phone2": "",
"faxNumber": "",
"url": "https://contoso.example",
"keyTechnologies": "PHP, MySQL",
"notes": "Preferred client",
"isHot": 1,
"departmentsCSV": "Engineering,HR"
}

## Contacts

Endpoint

- POST /index.php?m=contacts&a=add

Payload (from modules/contacts/ContactsUI.php::onAdd)

- Required: postback (always "postback"), companyID, firstName, lastName, title
- Optional: department, reportsTo, email1, email2, phoneWork, phoneCell, phoneOther, address, city, state, zip, isHot (checkbox), notes, departmentsCSV

Validation/notes

- companyID must be an existing company.
- Phone numbers are normalized where possible.
- departmentsCSV updates the company’s department list on submit.

Schema essentials (table contact)

- contact_id PK
- company_id FK, site_id
- first_name, last_name, title
- email1, email2; phone_work, phone_cell, phone_other
- address, city, state, zip
- is_hot (0/1), notes
- entered_by, owner, date_created, date_modified
- reports_to, company_department_id

Example payload
postback=postback&companyID=2&firstName=Pat&lastName=Lee&title=HR Manager&email1=pat.lee@example.com&phoneWork=2125550134&address=99 West St&city=NYC&state=NY&zip=10001&isHot=0&notes=Primary contact

JSON equivalent
{
"postback": "postback",
"companyID": 2,
"firstName": "Pat",
"lastName": "Lee",
"title": "HR Manager",
"department": "",
"reportsTo": "",
"email1": "pat.lee@example.com",
"email2": "",
"phoneWork": "2125550134",
"phoneCell": "",
"phoneOther": "",
"address": "99 West St",
"city": "NYC",
"state": "NY",
"zip": "10001",
"isHot": 0,
"notes": "Primary contact",
"departmentsCSV": ""
}

## Candidates

Endpoint

- POST /index.php?m=candidates&a=add

Payload (from modules/candidates/CandidatesUI.php::\_addCandidate)

- Required: postback (always "postback"), firstName, lastName
- Optional: middleName, email1, email2, phoneHome, phoneCell, phoneWork, address, city, state, zip, source, keySkills, dateAvailable (MM-DD-YY), currentEmployer, canRelocate (checkbox), currentPay, desiredPay, notes, webSite, bestTimeToCall, gender, race (EEO ethnic type id), veteran (EEO veteran type id), disability
- Resume options:
  - Upload file: file (multipart/form-data)
  - Paste text: documentText (when parsing enabled)
  - Text resume programmatic: textResumeBlock, textResumeFilename
  - Associate existing attachment: associatedAttachment (attachmentID)

Validation/notes

- dateAvailable must be MM-DD-YY; stored as YYYY-MM-DD.
- canRelocate and isHot are checkboxes; if present and truthy -> 1.
- EEO fields map to candidate.eeo\_\* columns: race and veteran expect integer IDs; gender and disability are stored as short strings.

Schema essentials (table candidate)

- candidate_id PK, site_id
- first_name, middle_name, last_name
- email1, email2; phone_home, phone_cell, phone_work
- address, city, state, zip
- source, key_skills, date_available, current_employer, can_relocate (0/1)
- current_pay, desired_pay, notes, web_site, best_time_to_call
- entered_by, owner, date_created, date_modified, is_hot (0/1)
- eeo_ethnic_type_id, eeo_veteran_type_id, eeo_disability_status, eeo_gender

Example payload
postback=postback&firstName=Jordan&lastName=Nguyen&email1=jordan@example.com&phoneCell=4155550199&city=San Francisco&state=CA&zip=94105&source=Referral&keySkills=PHP, MySQL, Linux&canRelocate=1&desiredPay=120000&bestTimeToCall=Afternoons

JSON equivalent
{
"postback": "postback",
"firstName": "Jordan",
"middleName": "",
"lastName": "Nguyen",
"email1": "jordan@example.com",
"email2": "",
"phoneHome": "",
"phoneCell": "4155550199",
"phoneWork": "",
"address": "",
"city": "San Francisco",
"state": "CA",
"zip": "94105",
"source": "Referral",
"keySkills": "PHP, MySQL, Linux",
"dateAvailable": "",
"currentEmployer": "",
"canRelocate": 1,
"currentPay": "",
"desiredPay": "120000",
"notes": "",
"webSite": "",
"bestTimeToCall": "Afternoons",
"gender": "",
"race": 3,
"veteran": 1,
"disability": "",
"textResumeBlock": "",
"textResumeFilename": "",
"associatedAttachment": ""
}

## Job Orders

Endpoint

- POST /index.php?m=joborders&a=add

Payload (from modules/joborders/JobOrdersUI.php::onAdd)

- Required: postback (always "postback"), companyID, recruiter, owner, openings, contactID (optional but validated), title, type, city, state
- Optional: companyJobID, duration, department, maxRate, salary, description, notes, isHot (checkbox), public (checkbox), startDate (MM-DD-YY), questionnaire (ID or 'none' if not used)

Validation/notes

- openings must be numeric.
- startDate if present must be MM-DD-YY; stored as YYYY-MM-DD.
- type is a code from JobOrderTypes: C (Contract), C2H (Contract To Hire), FL (Freelance), H (Hire).
- public may optionally include questionnaireID when enabled.

Schema essentials (table joborder)

- joborder_id PK
- recruiter, owner; contact_id, company_id
- client_job_id, title (not null), type (varchar code)
- description, notes, duration, rate_max, salary
- status (defaults 'Active'), is_hot (0/1), openings
- city, state, start_date, public (0/1), company_department_id
- openings_available, questionnaire_id, is_admin_hidden
- entered_by, site_id, date_created, date_modified

Example payload
postback=postback&companyID=2&contactID=3&recruiter=1&owner=1&openings=2&title=Senior PHP Developer&type=H&city=Austin&state=TX&salary=130000&isHot=1&public=1&description=Build and maintain ATS features.

JSON equivalent
{
"postback": "postback",
"companyID": 2,
"contactID": 3,
"recruiter": 1,
"owner": 1,
"openings": 2,
"title": "Senior PHP Developer",
"companyJobID": "",
"type": "H",
"city": "Austin",
"state": "TX",
"duration": "",
"department": "",
"maxRate": "",
"salary": "130000",
"description": "Build and maintain ATS features.",
"notes": "",
"isHot": 1,
"public": 1,
"startDate": "",
"questionnaire": "none"
}

## Events (Calendar)

Endpoint

- POST /index.php?m=calendar&a=addEvent

Payload (from modules/calendar/CalendarUI.php::onAddEvent)

- Required: postback (always "postback"), dateAdd (MM-DD-YY), type (event type id), title
- Optional: duration (minutes, default 30), allDay (0/1), hour, minute, meridiem (AM|PM) when timed, publicEntry (checkbox), reminderToggle (checkbox), sendEmail (email), reminderTime (int minutes), description

Validation/notes

- If allDay=1, time fields are ignored and event stored with date at 12:00AM.
- Event type ids (calendar_event_type): 100 Call, 200 Email, 300 Meeting, 400 Interview, 500 Personal, 600 Other.

Schema essentials (table calendar_event)

- calendar_event_id PK
- type, date (datetime), title, description
- all_day (0/1), duration, reminder_enabled (0/1), reminder_email, reminder_time
- public (0/1), entered_by, site_id, data_item_type/id (linkage), joborder_id
- date_created, date_modified

Example payload
postback=postback&dateAdd=10-31-25&allDay=0&type=300&hour=2&minute=30&meridiem=PM&title=Client kickoff&description=Meet with Contoso stakeholders&publicEntry=1&reminderToggle=1&sendEmail=me@example.com&reminderTime=30

JSON equivalent
{
"postback": "postback",
"dateAdd": "10-31-25",
"type": 300,
"duration": 30,
"allDay": 0,
"hour": 2,
"minute": 30,
"meridiem": "PM",
"publicEntry": 1,
"reminderToggle": 1,
"sendEmail": "me@example.com",
"reminderTime": 30,
"title": "Client kickoff",
"description": "Meet with Contoso stakeholders"
}

## Lists (Saved Lists)

Entry points (all via POST to /ajax.php with f specifying the list function)

- f=lists:newList

  - description (list name)
  - dataItemType (int; 100 Candidate, 200 Company, 300 Contact, 400 Job Order)

- f=lists:editListName

  - savedListID (int)
  - savedListName (string)

- f=lists:deleteList

  - savedListID (int)

- f=lists:addToLists
  - listsToAdd (CSV of list IDs)
  - itemsToAdd (CSV of item IDs)
  - dataItemType (int; see mapping above)

Validation/notes

- All IDs must be digits; server rejects invalid elements.
- addToLists batches inserts in chunks for performance.

Schema essentials

- saved_list: saved_list_id PK, description, data_item_type, site_id, is_dynamic, number_entries, datagrid_instance, parameters, created_by, date_created, date_modified
- saved_list_entry: saved_list_entry_id PK, saved_list_id, data_item_type, data_item_id, site_id, date_created
- data_item_type: 100 Candidate, 200 Company, 300 Contact, 400 Job Order

Example payloads

- Create list: f=lists:newList&description=Hot Candidates&dataItemType=100
- Add entries: f=lists:addToLists&listsToAdd=5&itemsToAdd=12,18,27&dataItemType=100

JSON equivalents

- Create list
  {
  "f": "lists:newList",
  "description": "Hot Candidates",
  "dataItemType": 100
  }
- Add entries
  {
  "f": "lists:addToLists",
  "listsToAdd": "5",
  "itemsToAdd": "12,18,27",
  "dataItemType": 100
  }

Mapping tables (quick reference)

Calendar event types

| id  | description |
| --- | ----------- |
| 100 | Call        |
| 200 | Email       |
| 300 | Meeting     |
| 400 | Interview   |
| 500 | Personal    |
| 600 | Other       |

List data item types

| id  | description |
| --- | ----------- |
| 100 | Candidate   |
| 200 | Company     |
| 300 | Contact     |
| 400 | Job Order   |

EEO ethnic types

| id  | type                      |
| --- | ------------------------- |
| 1   | American Indian           |
| 2   | Asian or Pacific Islander |
| 3   | Hispanic or Latino        |
| 4   | Non-Hispanic Black        |
| 5   | Non-Hispanic White        |

EEO veteran types

| id  | type                  |
| --- | --------------------- |
| 1   | No Veteran Status     |
| 2   | Eligible Veteran      |
| 3   | Disabled Veteran      |
| 4   | Eligible and Disabled |

## Reports (read‑only parameters)

Endpoints are GET and produce graphs or PDFs; useful to verify seeded data.

- Job Order Recruiting Summary PDF

  - GET /index.php?m=reports&a=generateJobOrderReportPDF
  - Params: siteName, companyName, jobOrderName, periodLine, accountManager, recruiter, notes, dataSet (CSV; defaults to 4,3,2,1)

- EEO Report Preview (graphs and stats)
  - GET /index.php?m=reports&a=generateEEOReportPreview
  - Params: period (week|month|all), status (rejected|placed|all)

Tip: Use these after seeding to confirm distributions and counts render correctly.

---

Quick seeding checklist per entity

- Companies: name, optional contact details. Capture companyID for linking.
- Contacts: companyID + firstName/lastName/title.
- Candidates: firstName/lastName minimum; attach resume via file or text when available.
- Job Orders: companyID/recruiter/owner/openings + title/type/city/state.
- Events: dateAdd/type/title; link to items via data_item_type/id if needed.
- Lists: create saved_list, then add saved_list_entry rows via addToLists.

All payload names above match the application’s expected POST parameter names.

## Bulk-import CSVs

CSV mapping files are provided in the `seed/` directory for convenience:

- `seed/calendar_event_types.csv`
- `seed/data_item_types.csv`
- `seed/eeo_ethnic_types.csv`
- `seed/eeo_veteran_types.csv`

Each has headers `id,description` (or `id,type`) and can be loaded by your seeding tool.

## PowerShell seeding script

A reusable script lives at `seed/script.ps1`. It:

- Logs in and maintains a session cookie
- Seeds a Company, Contact, Candidate, Job Order, Calendar Event
- Creates a Saved List and adds the Candidate to it

Usage (PowerShell 5.1 on Windows)

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\seed\script.ps1 -BaseUrl "http://localhost:80" -Username "john@mycompany.net" -Password "john99" -SiteName "CATS" -OwnerId 1 -RecruiterId 1
```

Parameters

- BaseUrl: Root of your OpenCATS (e.g., http://localhost)
- Username/Password/SiteName: Your login
- OwnerId/RecruiterId: User IDs for ownership and recruiting (defaults 1)

Outputs: prints created IDs (companyID, contactID, candidateID, jobOrderID, savedListID) and HTTP status for each step.
