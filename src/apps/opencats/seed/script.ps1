param(
  [Parameter(Mandatory=$true)] [string]$BaseUrl,
  [Parameter(Mandatory=$true)] [string]$Username,
  [Parameter(Mandatory=$true)] [string]$Password,
  [Parameter(Mandatory=$false)] [string]$SiteName = "",
  [Parameter(Mandatory=$false)] [int]$OwnerId = 1,
  [Parameter(Mandatory=$false)] [int]$RecruiterId = 1
)

# Basic helpers
function Join-Url([string]$base, [string]$path) {
  if ($path.StartsWith('/')) { return "$base$path" }
  if ($base.EndsWith('/')) { return "$base/$path" }
  return "$base/$path"
}

function Get-QueryParam([Uri]$uri, [string]$name) {
  $query = [System.Web.HttpUtility]::ParseQueryString($uri.Query)
  return $query[$name]
}

function Get-EntityIdFromResponse([string]$content, [string]$pattern) {
  $matches = Select-String -InputObject $content -Pattern $pattern -AllMatches
  if ($matches.Matches.Count -gt 0) {
    return $matches.Matches[0].Groups[1].Value
  }
  return $null
}

function Get-LatestEntityId([string]$BaseUrl, [Microsoft.PowerShell.Commands.WebRequestSession]$session, [string]$module, [string]$entity) {
  try {
    # Try to visit the module's main page and extract the most recent entity ID
    $listUrl = Join-Url $BaseUrl "/index.php?m=$module"
    $listResp = Invoke-WebRequest -Uri $listUrl -WebSession $session -TimeoutSec 10
    
    # Look for entity view URLs like "index.php?m=companies&a=show&companyID=123"
    $pattern = switch ($entity) {
      'company' { 'companyID=(\d+)' }
      'contact' { 'contactID=(\d+)' }
      'candidate' { 'candidateID=(\d+)' }
      'joborder' { 'jobOrderID=(\d+)' }
      default { "${entity}ID=(\d+)" }
    }
    
    $matches = Select-String -InputObject $listResp.Content -Pattern $pattern -AllMatches
    if ($matches.Matches.Count -gt 0) {
      # Return the highest ID found (likely the most recent)
      $ids = $matches.Matches | ForEach-Object { [int]$_.Groups[1].Value } | Sort-Object -Descending
      return $ids[0]
    }
  } catch {
    Write-Warning "Failed to extract latest $entity ID from listing page: $_"
  }
  return $null
}

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Web

# Maintain a cookie session across requests
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

Write-Host "Logging in..."
$loginUrl = Join-Url $BaseUrl "/index.php?m=login&a=attemptLogin"
$loginBody = @{ username = $Username; password = $Password }
if ($SiteName -ne "") { $loginBody.siteName = $SiteName }
$loginResp = Invoke-WebRequest -Uri $loginUrl -Method Post -Body $loginBody -WebSession $session -ContentType 'application/x-www-form-urlencoded' -MaximumRedirection 5 -ErrorAction Stop
Write-Host ("Login status: {0}" -f $loginResp.StatusCode)

# Seed Company
Write-Host "Creating Company..."
$companyUrl = Join-Url $BaseUrl "/index.php?m=companies&a=add"
$companyBody = @{ 
  postback = 'postback'
  name = 'Contoso LLC'; address = '1 Main St'; city = 'Austin'; state = 'TX'; zip = '78701';
  phone1 = '5125550100'; url = 'https://contoso.example'; isHot = '1'; keyTechnologies = 'PHP, MySQL'; notes = 'Preferred client'
}
$companyResp = Invoke-WebRequest -Uri $companyUrl -Method Post -Body $companyBody -WebSession $session -ContentType 'application/x-www-form-urlencoded' -MaximumRedirection 5
Write-Host "Company create status: $($companyResp.StatusCode)"
$companyId = Get-QueryParam $companyResp.BaseResponse.ResponseUri 'companyID'
if (-not $companyId) { 
  # Try to extract from HTML content - look for companyID patterns in forms or URLs
  $companyId = Get-EntityIdFromResponse $companyResp.Content 'companyID[=:](\d+)|company_id[=:](\d+)'
  if (-not $companyId) {
    # Try to get the latest company ID from the companies listing
    $companyId = Get-LatestEntityId $BaseUrl $session 'companies' 'company'
    if (-not $companyId) {
      Write-Warning "Could not resolve companyID from any method."
      $companyId = "1"  # Fallback assumption for demo
    }
  }
}
Write-Host "companyID=$companyId"

# Seed Contact (requires companyID)
Write-Host "Creating Contact..."
$contactUrl = Join-Url $BaseUrl "/index.php?m=contacts&a=add"
$contactBody = @{
  postback = 'postback'
  companyID = $companyId; firstName = 'Pat'; lastName = 'Lee'; title = 'HR Manager';
  email1 = 'pat.lee@example.com'; phoneWork = '2125550134'; address = '99 West St'; city = 'NYC'; state = 'NY'; zip = '10001'; isHot = '0'; notes = 'Primary contact'
}
$contactResp = Invoke-WebRequest -Uri $contactUrl -Method Post -Body $contactBody -WebSession $session -ContentType 'application/x-www-form-urlencoded' -MaximumRedirection 5
Write-Host "Contact create status: $($contactResp.StatusCode)"
$contactId = Get-QueryParam $contactResp.BaseResponse.ResponseUri 'contactID'
if (-not $contactId) { 
  $contactId = Get-EntityIdFromResponse $contactResp.Content 'contactID[=:](\d+)|contact_id[=:](\d+)'
  if (-not $contactId) {
    $contactId = Get-LatestEntityId $BaseUrl $session 'contacts' 'contact'
    if (-not $contactId) {
      Write-Warning "Could not resolve contactID from any method."
      $contactId = "1"  # Fallback assumption for demo
    }
  }
}
Write-Host "contactID=$contactId"

# Seed Candidate
Write-Host "Creating Candidate..."
$candUrl = Join-Url $BaseUrl "/index.php?m=candidates&a=add"
$candBody = @{
  postback = 'postback'
  firstName = 'Jordan'; lastName = 'Nguyen'; email1 = 'jordan@example.com'; phoneCell = '4155550199';
  city = 'San Francisco'; state = 'CA'; zip = '94105'; source = 'Referral'; keySkills = 'PHP, MySQL, Linux'; canRelocate = '1'; desiredPay = '120000'; bestTimeToCall = 'Afternoons'
}
$candResp = Invoke-WebRequest -Uri $candUrl -Method Post -Body $candBody -WebSession $session -ContentType 'application/x-www-form-urlencoded' -MaximumRedirection 5
Write-Host "Candidate create status: $($candResp.StatusCode)"
$candidateId = Get-QueryParam $candResp.BaseResponse.ResponseUri 'candidateID'
if (-not $candidateId) { 
  $candidateId = Get-EntityIdFromResponse $candResp.Content 'candidateID[=:](\d+)|candidate_id[=:](\d+)'
  if (-not $candidateId) {
    $candidateId = Get-LatestEntityId $BaseUrl $session 'candidates' 'candidate'
    if (-not $candidateId) {
      Write-Warning "Could not resolve candidateID from any method."
      $candidateId = "1"  # Fallback assumption for demo
    }
  }
}
Write-Host "candidateID=$candidateId"

# Seed Job Order (requires company and contact)
Write-Host "Creating Job Order..."
$joUrl = Join-Url $BaseUrl "/index.php?m=joborders&a=add"
$joBody = @{
  postback = 'postback'
  companyID = $companyId; contactID = $contactId; recruiter = $RecruiterId; owner = $OwnerId; openings = '2';
  title = 'Senior PHP Developer'; type = 'H'; city = 'Austin'; state = 'TX'; salary = '130000'; isHot = '1'; public = '1'; description = 'Build and maintain ATS features.'
}
$joResp = Invoke-WebRequest -Uri $joUrl -Method Post -Body $joBody -WebSession $session -ContentType 'application/x-www-form-urlencoded' -MaximumRedirection 5
Write-Host "Job Order create status: $($joResp.StatusCode)"
$jobOrderId = Get-QueryParam $joResp.BaseResponse.ResponseUri 'jobOrderID'
if (-not $jobOrderId) { 
  $jobOrderId = Get-EntityIdFromResponse $joResp.Content 'jobOrderID[=:](\d+)|joborder_id[=:](\d+)'
  if (-not $jobOrderId) {
    $jobOrderId = Get-LatestEntityId $BaseUrl $session 'joborders' 'joborder'
    if (-not $jobOrderId) {
      Write-Warning "Could not resolve jobOrderID from any method."
      $jobOrderId = "1"  # Fallback assumption for demo
    }
  }
}
Write-Host "jobOrderID=$jobOrderId"

# Seed Calendar Event
Write-Host "Creating Event..."
$evtUrl = Join-Url $BaseUrl "/index.php?m=calendar&a=addEvent"
$evtBody = @{
  postback = 'postback'
  dateAdd = (Get-Date).ToString('MM-dd-yy'); allDay = '0'; type = '300'; hour = '2'; minute = '30'; meridiem = 'PM';
  title = 'Client kickoff'; description = 'Meet with Contoso stakeholders'; publicEntry = '1'; reminderToggle = '1'; sendEmail = $Username; reminderTime = '30'
}
$evtResp = Invoke-WebRequest -Uri $evtUrl -Method Post -Body $evtBody -WebSession $session -ContentType 'application/x-www-form-urlencoded' -MaximumRedirection 5
Write-Host ("Event create status: {0}" -f $evtResp.StatusCode)

# Create Saved List and add Candidate
Write-Host "Creating Saved List..."
$ajaxUrl = Join-Url $BaseUrl "/ajax.php"
$newListResp = Invoke-WebRequest -Uri $ajaxUrl -Method Post -Body @{ f = 'lists:newList'; description = 'Hot Candidates'; dataItemType = '100' } -WebSession $session -ContentType 'application/x-www-form-urlencoded'
Write-Host ("New list status: {0}" -f $newListResp.StatusCode)

# Fetch the new list ID by querying the lists page (fallback approach)
# Alternatively, you can manually set $savedListId if known
$savedListId = $null
try {
  $listsPage = Invoke-WebRequest -Uri (Join-Url $BaseUrl '/index.php?m=lists&a=listByView') -WebSession $session
  # Best-effort parse: look for savedListID in links
  $matches = Select-String -InputObject $listsPage.Content -Pattern 'savedListID=(\d+)' -AllMatches
  if ($matches.Matches.Count -gt 0) { $savedListId = $matches.Matches[0].Groups[1].Value }
} catch {}

if (-not $savedListId) { Write-Warning "Could not detect savedListID; addToLists step will be skipped." }
else {
  Write-Host "Adding candidate $candidateId to list $savedListId..."
  $addToListResp = Invoke-WebRequest -Uri $ajaxUrl -Method Post -Body @{ f = 'lists:addToLists'; listsToAdd = $savedListId; itemsToAdd = $candidateId; dataItemType = '100' } -WebSession $session -ContentType 'application/x-www-form-urlencoded'
  Write-Host ("addToLists status: {0}" -f $addToListResp.StatusCode)
}

Write-Host "Seeding complete."