$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open('C:\Users\reach\OneDrive\Desktop\Resume\arvind_resume_Capgemini.pdf', $false, $true)
    Write-Output "PAGES=$($doc.ComputeStatistics(2))"
    Write-Output $doc.Content.Text
    $doc.Close($false)
} finally {
    $word.Quit()
}
