# OpenCATS API Payloads for Data Seeding

This document focuses on POST request payloads and minimal schemas for the core entities you asked to seed: job orders, companies, candidates, contacts, events (calendar), lists, and reports (read-only parameters). It's distilled from the application handlers and database schema.

## Important Notes

- Unless otherwise noted, forms post as `application/x-www-form-urlencoded`.
- **CRITICAL**: All form submissions MUST include `postback=postback` hidden field, or the request will only display the form page instead of processing the submission.
- Extra fields: many entities support custom "extra fields" stored separately; these are updated after insert using the entity's ExtraFields helper. Include them as additional POST fields if configured in your instance.

## Companies

### Endpoint

- POST `/index.php?m=companies&a=add`

### Payload

(from `modules/companies/CompaniesUI.php::onAdd`)

- **Required**: `postback` (always "postback"), `name`
- **Optional**: `address`, `city`, `state`, `zip`, `phone1`, `phone2`, `faxNumber`, `url`, `keyTechnologies`, `notes`, `isHot` (checkbox), `departmentsCSV` (CSV of department names)

### Validation/Notes

- Phone numbers are normalized where possible.
- `url` is normalized if parseable.

### Schema Essentials

(table `company`)

- `company_id` PK
- `name` (varchar, not null)
- `address`, `city`, `state`, `zip`
- `phone1`, `phone2`, `fax_number`
- `url`, `key_technologies`, `notes`
- `entered_by`, `owner`, `date_created`, `date_modified`
- `is_hot` (0/1), `default_company` (0/1)

### Example Payload

```
postback=postback&name=Contoso LLC&address=1 Main St&city=Austin&state=TX&zip=78701&phone1=5125550100&url=https://contoso.example&isHot=1&keyTechnologies=PHP, MySQL&notes=Preferred client
```

### JSON Equivalent

```json
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
```

## Contacts

### Endpoint

- POST `/index.php?m=contacts&a=add`

### Payload

(from `modules/contacts/ContactsUI.php::onAdd`)

- **Required**: `postback` (always "postback"), `companyID`, `firstName`, `lastName`, `title`
- **Optional**: `department`, `reportsTo`, `email1`, `email2`, `phoneWork`, `phoneCell`, `phoneOther`, `address`, `city`, `state`, `zip`, `isHot` (checkbox), `notes`, `departmentsCSV`

### Validation/Notes

- `companyID` must be an existing company.
- Phone numbers are normalized where possible.
- `departmentsCSV` updates the company's department list on submit.

### Schema Essentials

(table `contact`)

- `contact_id` PK
- `company_id` FK, `site_id`
- `first_name`, `last_name`, `title`
- `email1`, `email2`; `phone_work`, `phone_cell`, `phone_other`
- `address`, `city`, `state`, `zip`
- `is_hot` (0/1), `notes`
- `entered_by`, `owner`, `date_created`, `date_modified`
- `reports_to`, `company_department_id`

### Example Payload

```
postback=postback&companyID=2&firstName=Pat&lastName=Lee&title=HR Manager&email1=pat.lee@example.com&phoneWork=2125550134&address=99 West St&city=NYC&state=NY&zip=10001&isHot=0&notes=Primary contact
```

### JSON Equivalent

```json
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
```

## Candidates

### Endpoint

- POST `/index.php?m=candidates&a=add`

### Payload

(from `modules/candidates/CandidatesUI.php::_addCandidate`)

- **Required**: `postback` (always "postback"), `firstName`, `lastName`
- **Optional**: `middleName`, `email1`, `email2`, `phoneHome`, `phoneCell`, `phoneWork`, `address`, `city`, `state`, `zip`, `source`, `keySkills`, `dateAvailable` (MM-DD-YY), `currentEmployer`, `canRelocate` (checkbox), `currentPay`, `desiredPay`, `notes`, `webSite`, `bestTimeToCall`, `gender`, `race` (EEO ethnic type id), `veteran` (EEO veteran type id), `disability`
- **Resume options**:
  - Upload file: `file` (multipart/form-data)
  - Paste text: `documentText` (when parsing enabled)
  - Text resume programmatic: `textResumeBlock`, `textResumeFilename`
  - Associate existing attachment: `associatedAttachment` (attachmentID)

### Validation/Notes

- `dateAvailable` must be MM-DD-YY; stored as YYYY-MM-DD.
- `canRelocate` and `isHot` are checkboxes; if present and truthy → 1.
- EEO fields map to `candidate.eeo_*` columns: `race` and `veteran` expect integer IDs; `gender` and `disability` are stored as short strings.

### Schema Essentials

(table `candidate`)

- `candidate_id` PK, `site_id`
- `first_name`, `middle_name`, `last_name`
- `email1`, `email2`; `phone_home`, `phone_cell`, `phone_work`
- `address`, `city`, `state`, `zip`
- `source`, `key_skills`, `date_available`, `current_employer`, `can_relocate` (0/1)
- `current_pay`, `desired_pay`, `notes`, `web_site`, `best_time_to_call`
- `entered_by`, `owner`, `date_created`, `date_modified`, `is_hot` (0/1)
- `eeo_ethnic_type_id`, `eeo_veteran_type_id`, `eeo_disability_status`, `eeo_gender`

### Example Payload

```
postback=postback&firstName=Jordan&lastName=Nguyen&email1=jordan@example.com&phoneCell=4155550199&city=San Francisco&state=CA&zip=94105&source=Referral&keySkills=PHP, MySQL, Linux&canRelocate=1&desiredPay=120000&bestTimeToCall=Afternoons
```

### JSON Equivalent

```json
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
```

## Job Orders

### Endpoint

- POST `/index.php?m=joborders&a=add`

### Payload

(from `modules/joborders/JobOrdersUI.php::onAdd`)

- **Required**: `postback` (always "postback"), `companyID`, `recruiter`, `owner`, `openings`, `contactID` (optional but validated), `title`, `type`, `city`, `state`
- **Optional**: `companyJobID`, `duration`, `department`, `maxRate`, `salary`, `description`, `notes`, `isHot` (checkbox), `public` (checkbox), `startDate` (MM-DD-YY), `questionnaire` (ID or 'none' if not used)

### Validation/Notes

- `openings` must be numeric.
- `startDate` if present must be MM-DD-YY; stored as YYYY-MM-DD.
- `type` is a code from JobOrderTypes: C (Contract), C2H (Contract To Hire), FL (Freelance), H (Hire).
- `public` may optionally include questionnaireID when enabled.

### Schema Essentials

(table `joborder`)

- `joborder_id` PK
- `recruiter`, `owner`; `contact_id`, `company_id`
- `client_job_id`, `title` (not null), `type` (varchar code)
- `description`, `notes`, `duration`, `rate_max`, `salary`
- `status` (defaults 'Active'), `is_hot` (0/1), `openings`
- `city`, `state`, `start_date`, `public` (0/1), `company_department_id`
- `openings_available`, `questionnaire_id`, `is_admin_hidden`
- `entered_by`, `site_id`, `date_created`, `date_modified`

### Example Payload

```
postback=postback&companyID=2&contactID=3&recruiter=1&owner=1&openings=2&title=Senior PHP Developer&type=H&city=Austin&state=TX&salary=130000&isHot=1&public=1&description=Build and maintain ATS features.
```

### JSON Equivalent

```json
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
```

## Events (Calendar)

### Endpoint

- POST `/index.php?m=calendar&a=addEvent`

### Payload

(from `modules/calendar/CalendarUI.php::onAddEvent`)

- **Required**: `postback` (always "postback"), `dateAdd` (MM-DD-YY), `type` (event type id), `title`
- **Optional**: `duration` (minutes, default 30), `allDay` (0/1), `hour`, `minute`, `meridiem` (AM|PM) when timed, `publicEntry` (checkbox), `reminderToggle` (checkbox), `sendEmail` (email), `reminderTime` (int minutes), `description`

### Validation/Notes

- If `allDay=1`, time fields are ignored and event stored with date at 12:00AM.
- Event type ids (`calendar_event_type`): 100 Call, 200 Email, 300 Meeting, 400 Interview, 500 Personal, 600 Other.

### Schema Essentials

(table `calendar_event`)

- `calendar_event_id` PK
- `type`, `date` (datetime), `title`, `description`
- `all_day` (0/1), `duration`, `reminder_enabled` (0/1), `reminder_email`, `reminder_time`
- `public` (0/1), `entered_by`, `site_id`, `data_item_type/id` (linkage), `joborder_id`
- `date_created`, `date_modified`

### Example Payload

```
postback=postback&dateAdd=10-31-25&allDay=0&type=300&hour=2&minute=30&meridiem=PM&title=Client kickoff&description=Meet with Contoso stakeholders&publicEntry=1&reminderToggle=1&sendEmail=me@example.com&reminderTime=30
```

### JSON Equivalent

```json
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
```

## Lists (Saved Lists)

### Entry Points

(all via POST to `/ajax.php` with `f` specifying the list function)

- **`f=lists:newList`**

  - `description` (list name)
  - `dataItemType` (int; 100 Candidate, 200 Company, 300 Contact, 400 Job Order)

- **`f=lists:editListName`**

  - `savedListID` (int)
  - `savedListName` (string)

- **`f=lists:deleteList`**

  - `savedListID` (int)

- **`f=lists:addToLists`**
  - `listsToAdd` (CSV of list IDs)
  - `itemsToAdd` (CSV of item IDs)
  - `dataItemType` (int; see mapping above)

### Validation/Notes

- All IDs must be digits; server rejects invalid elements.
- `addToLists` batches inserts in chunks for performance.

### Schema Essentials

- **`saved_list`**: `saved_list_id` PK, `description`, `data_item_type`, `site_id`, `is_dynamic`, `number_entries`, `datagrid_instance`, `parameters`, `created_by`, `date_created`, `date_modified`
- **`saved_list_entry`**: `saved_list_entry_id` PK, `saved_list_id`, `data_item_type`, `data_item_id`, `site_id`, `date_created`
- **`data_item_type`**: 100 Candidate, 200 Company, 300 Contact, 400 Job Order

### Example Payloads

- **Create list**: `f=lists:newList&description=Hot Candidates&dataItemType=100`
- **Add entries**: `f=lists:addToLists&listsToAdd=5&itemsToAdd=12,18,27&dataItemType=100`

### JSON Equivalents

**Create list**

```json
{
	"f": "lists:newList",
	"description": "Hot Candidates",
	"dataItemType": 100
}
```

**Add entries**

```json
{
	"f": "lists:addToLists",
	"listsToAdd": "5",
	"itemsToAdd": "12,18,27",
	"dataItemType": 100
}
```

## Mapping Tables (Quick Reference)

### Calendar Event Types

| ID  | Description | Enum Value                    |
| --- | ----------- | ----------------------------- |
| 100 | Call        | `OpenCATSEventType.CALL`      |
| 200 | Email       | `OpenCATSEventType.EMAIL`     |
| 300 | Meeting     | `OpenCATSEventType.MEETING`   |
| 400 | Interview   | `OpenCATSEventType.INTERVIEW` |
| 500 | Personal    | `OpenCATSEventType.PERSONAL`  |
| 600 | Other       | `OpenCATSEventType.OTHER`     |

### List Data Item Types

| ID  | Description | Enum Value                       |
| --- | ----------- | -------------------------------- |
| 100 | Candidate   | `OpenCATSDataItemType.CANDIDATE` |
| 200 | Company     | `OpenCATSDataItemType.COMPANY`   |
| 300 | Contact     | `OpenCATSDataItemType.CONTACT`   |
| 400 | Job Order   | `OpenCATSDataItemType.JOB_ORDER` |

### Job Order Types

| Code | Description      | Enum Value                         |
| ---- | ---------------- | ---------------------------------- |
| C    | Contract         | `OpenCATSJobType.CONTRACT`         |
| C2H  | Contract to Hire | `OpenCATSJobType.CONTRACT_TO_HIRE` |
| FL   | Freelance        | `OpenCATSJobType.FREELANCE`        |
| H    | Hire             | `OpenCATSJobType.HIRE`             |

### EEO Ethnic Types

| ID  | Type                      | Enum Value                                     |
| --- | ------------------------- | ---------------------------------------------- |
| 1   | American Indian           | `OpenCATSEEOEthnicType.AMERICAN_INDIAN`        |
| 2   | Asian or Pacific Islander | `OpenCATSEEOEthnicType.ASIAN_PACIFIC_ISLANDER` |
| 3   | Hispanic or Latino        | `OpenCATSEEOEthnicType.HISPANIC_LATINO`        |
| 4   | Non-Hispanic Black        | `OpenCATSEEOEthnicType.NON_HISPANIC_BLACK`     |
| 5   | Non-Hispanic White        | `OpenCATSEEOEthnicType.NON_HISPANIC_WHITE`     |

### EEO Veteran Types

| ID  | Type                  | Enum Value                                     |
| --- | --------------------- | ---------------------------------------------- |
| 1   | No Veteran Status     | `OpenCATSEEOVeteranType.NO_VETERAN_STATUS`     |
| 2   | Eligible Veteran      | `OpenCATSEEOVeteranType.ELIGIBLE_VETERAN`      |
| 3   | Disabled Veteran      | `OpenCATSEEOVeteranType.DISABLED_VETERAN`      |
| 4   | Eligible and Disabled | `OpenCATSEEOVeteranType.ELIGIBLE_AND_DISABLED` |

### Candidate-Job Order Status

| ID   | Stage          | Enum Value                                       | Description                            |
| ---- | -------------- | ------------------------------------------------ | -------------------------------------- |
| 100  | No Contact     | `OpenCATSCandidateJobOrderStatus.NO_CONTACT`     | Candidate identified but not contacted |
| 200  | Contacted      | `OpenCATSCandidateJobOrderStatus.CONTACTED`      | Initial contact made                   |
| 300  | Submitted      | `OpenCATSCandidateJobOrderStatus.SUBMITTED`      | Resume submitted to client             |
| 400  | Applied        | `OpenCATSCandidateJobOrderStatus.APPLIED`        | Candidate applied for position         |
| 500  | Interviewing   | `OpenCATSCandidateJobOrderStatus.INTERVIEWING`   | In interview process                   |
| 600  | Offer Extended | `OpenCATSCandidateJobOrderStatus.OFFER_EXTENDED` | Job offer sent to candidate            |
| 700  | Offer Accepted | `OpenCATSCandidateJobOrderStatus.OFFER_ACCEPTED` | Candidate accepted offer               |
| 800  | Offer Declined | `OpenCATSCandidateJobOrderStatus.OFFER_DECLINED` | Candidate declined offer               |
| 900  | Placed         | `OpenCATSCandidateJobOrderStatus.PLACED`         | Candidate successfully placed          |
| 1000 | Rejected       | `OpenCATSCandidateJobOrderStatus.REJECTED`       | Candidate rejected or withdrew         |

---

## Data Generation Order & Relationships

### While Installing

1. **Database Host** : opencatsdb
2. **Database Name** : cats
3. **Database User** : dev
4. **Database Password** : dev

### Generation Sequence

1. **Companies** → Base entities (foundation for all other data)
2. **Contacts** → Linked to companies via `companyID`
3. **Candidates** → Independent entities with realistic skills matching job market
4. **Job Orders** → Linked to companies and contacts
5. **Candidate-Job Order Associations** → Many-to-many relationships between candidates and job orders
6. **Events** → Can reference any of the above entities
7. **Lists** → Can contain any entity type (candidates, companies, contacts, job orders)

### Key Relationships

#### Direct Relationships

- **Contacts** → **Companies**: `contact.companyID` references `company.id`
  - Each contact belongs to one company
- **Job Orders** → **Companies**: `joborder.companyID` references `company.id`
  - Each job order belongs to one company
- **Job Orders** → **Contacts**: `joborder.contactID` references `contact.id`
  - Each job order has a primary contact person

#### Many-to-Many Relationships

- **Candidates** ↔ **Job Orders**: Through `candidate_joborder` junction table
  - `candidate_joborder.candidate_id` references `candidate.id`
  - `candidate_joborder.joborder_id` references `joborder.id`
  - `candidate_joborder.status` indicates pipeline stage (100-1000)
  - One candidate can apply to multiple job orders
  - One job order can have multiple candidates
  - Typical association: 1-8 candidates per job order

#### Flexible Relationships

- **Events** → **Any Entity**: `event.dataItemType` + `event.dataItemID` references any entity
  - Can reference candidates, companies, contacts, or job orders
- **Lists** → **Any Entity**: `list.dataItemType` + `list.dataItemID` references any entity
  - Can contain candidates (100), companies (200), contacts (300), or job orders (400)

## Reports (Read-Only Parameters)

Endpoints are GET and produce graphs or PDFs; useful to verify seeded data.

### Job Order Recruiting Summary PDF

- **GET** `/index.php?m=reports&a=generateJobOrderReportPDF`
- **Params**: `siteName`, `companyName`, `jobOrderName`, `periodLine`, `accountManager`, `recruiter`, `notes`, `dataSet` (CSV; defaults to 4,3,2,1)

### EEO Report Preview (graphs and stats)

- **GET** `/index.php?m=reports&a=generateEEOReportPreview`
- **Params**: `period` (week|month|all), `status` (rejected|placed|all)

> **Tip**: Use these after seeding to confirm distributions and counts render correctly.

---

## Advanced Seeding Features

### Candidate-Job Order Junction Table Seeding

The `candidate_joborder` table creates many-to-many relationships between candidates and job orders, representing the hiring pipeline.

#### Implementation

**Module**: `src/apps/opencats/core/candidate_joborder.py`

**Function**: `seed_candidate_joborder()`

**Process**:
1. Retrieves all seeded candidates and job orders from OpenCATS
2. For each job order, randomly selects 1-8 candidates
3. Assigns realistic pipeline status to each association
4. Uses AJAX endpoint `candidates:addToPipeline` to create associations

**Status Distribution** (weighted for realism):
- 5% - No Contact (100)
- 15% - Contacted (200)
- 20% - Submitted (300)
- 25% - Applied (400)
- 20% - Interviewing (500)
- 5% - Offer Extended (600)
- 3% - Offer Accepted (700)
- 3% - Offer Declined (800)
- 2% - Placed (900)
- 2% - Rejected (1000)

**API Endpoint**: 
- AJAX: `POST /ajax.php?f=candidates:addToPipeline`
- Parameters: `candidateID`, `jobOrderID`, `status`

### Billing Contact Assignment

Companies can designate one contact as their billing contact, stored in `company.billing_contact`.

#### Implementation

**Module**: `src/apps/opencats/core/companies.py`

**Function**: `update_companies_billing_contacts()`

**Process**:
1. Identifies billing contacts from generated data (`isBillingContact` flag)
2. Retrieves actual OpenCATS company and contact IDs
3. Matches contacts to companies by name and company association
4. Updates company records with proper billing contact ID

**Database Field**: `company.billing_contact` (INT, references `contact.contact_id`)

**API Endpoint**: 
- POST: `/index.php?m=companies&a=edit&companyID={id}`
- Parameter: `billingContact` (contact ID)

**Key Fix**: Previously used incorrect IDs from generated data; now properly retrieves and maps actual OpenCATS entity IDs.

### Contact Reporting Hierarchy

Contacts have a hierarchical reporting structure where non-billing contacts report to the billing contact.

#### Implementation

**Module**: `src/apps/opencats/core/contacts.py`

**Function**: `update_contacts_reports_to()`

**Business Rules**:
- Billing contacts have `reports_to = NULL` (top of hierarchy)
- Other contacts at the same company have `reports_to = billing_contact_id`
- Each company can have only one billing contact
- Non-billing contacts automatically report to the billing contact

**Process**:
1. Groups contacts by company
2. Identifies billing contacts per company
3. Retrieves actual OpenCATS contact and company IDs
4. For billing contacts: clears `reports_to` field
5. For other contacts: sets `reports_to` to billing contact's ID

**Database Field**: `contact.reports_to` (INT, references `contact.contact_id`, default -1)

**API Endpoint**: 
- POST: `/index.php?m=contacts&a=edit&contactID={id}`
- Parameter: `reportsTo` (contact ID or empty string)

**Seeding Sequence**: 
1. Seed all contacts without `reports_to` relationships
2. Run `update_contacts_reports_to()` to establish hierarchy
3. Run `update_companies_billing_contacts()` to link companies to billing contacts

### Seeding Order (Updated)

The complete seeding sequence with relationship management:

1. **Companies** - Base entities
2. **Contacts** - Linked to companies (without reports_to initially)
3. **Update Contacts Reports To** - Establish contact hierarchy
4. **Update Companies Billing Contacts** - Link companies to billing contacts
5. **Candidates** - Independent entities
6. **Job Orders** - Linked to companies and contacts
7. **Candidate-Job Order Associations** - Junction table relationships
8. **Events** - Can reference any entity
9. **Lists** - Can contain any entity type

### API Routes for Relationships

#### Add Candidate to Job Order Pipeline
```
POST /ajax.php
f=candidates:addToPipeline
candidateID={candidate_id}
jobOrderID={joborder_id}
status={pipeline_status_id}
```

#### Update Company Billing Contact
```
POST /index.php?m=companies&a=edit&companyID={company_id}
postback=postback
billingContact={contact_id}
```

#### Update Contact Reporting Relationship
```
POST /index.php?m=contacts&a=edit&contactID={contact_id}
postback=postback
reportsTo={manager_contact_id}
```

### Database Schema Reference

#### candidate_joborder Table
```sql
CREATE TABLE `candidate_joborder` (
  `candidate_joborder_id` INT AUTO_INCREMENT PRIMARY KEY,
  `candidate_id` INT NOT NULL,
  `joborder_id` INT NOT NULL,
  `site_id` INT NOT NULL,
  `status` INT NOT NULL DEFAULT 0,
  `date_submitted` DATETIME,
  `date_created` DATETIME,
  `date_modified` DATETIME,
  `rating_value` INT(5),
  `added_by` INT,
  KEY `IDX_candidate_id` (`candidate_id`),
  KEY `IDX_joborder_id` (`joborder_id`),
  KEY `IDX_status_special` (`site_id`, `status`)
);
```

#### company Table (relevant fields)
```sql
CREATE TABLE `company` (
  `company_id` INT AUTO_INCREMENT PRIMARY KEY,
  `billing_contact` INT DEFAULT NULL,  -- References contact.contact_id
  `name` VARCHAR(64) NOT NULL,
  -- other fields...
);
```

#### contact Table (relevant fields)
```sql
CREATE TABLE `contact` (
  `contact_id` INT AUTO_INCREMENT PRIMARY KEY,
  `company_id` INT NOT NULL,
  `reports_to` INT DEFAULT -1,  -- References contact.contact_id
  `first_name` VARCHAR(64) NOT NULL,
  `last_name` VARCHAR(64) NOT NULL,
  -- other fields...
);
```

---

## Quick Seeding Checklist Per Entity

- **Companies**: `name`, optional contact details. Capture `companyID` for linking.
- **Contacts**: `companyID` + `firstName`/`lastName`/`title`.
- **Candidates**: `firstName`/`lastName` minimum; attach resume via file or text when available.
- **Job Orders**: `companyID`/`recruiter`/`owner`/`openings` + `title`/`type`/`city`/`state`.
- **Events**: `dateAdd`/`type`/`title`; link to items via `data_item_type`/`id` if needed.
- **Lists**: create `saved_list`, then add `saved_list_entry` rows via `addToLists`.

> **Note**: All payload names above match the application's expected POST parameter names.

## Bulk-Import CSVs

CSV mapping files are provided in the `test/seed/` directory for convenience:

- `test/seed/calendar_event_types.csv`
- `test/seed/data_item_types.csv`
- `test/seed/eeo_ethnic_types.csv`
- `test/seed/eeo_veteran_types.csv`

Each has headers `id,description` (or `id,type`) and can be loaded by your seeding tool.

## PowerShell Seeding Script

A reusable script lives at `test/seed/script.ps1`. It:

- Logs in and maintains a session cookie
- Seeds a Company, Contact, Candidate, Job Order, Calendar Event
- Creates a Saved List and adds the Candidate to it

### Usage

(PowerShell 5.1 on Windows)

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\seed\script.ps1 -BaseUrl "http://localhost:80" -Username "john@mycompany.net" -Password "john99" -SiteName "CATS" -OwnerId 1 -RecruiterId 1
```

### Parameters

- **BaseUrl**: Root of your OpenCATS (e.g., http://localhost)
- **Username/Password/SiteName**: Your login credentials
- **OwnerId/RecruiterId**: User IDs for ownership and recruiting (defaults to 1)

### Outputs

Prints created IDs (`companyID`, `contactID`, `candidateID`, `jobOrderID`, `savedListID`) and HTTP status for each step.
