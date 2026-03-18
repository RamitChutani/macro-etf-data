Attribute VB_Name = "RegionFilter"
' Region Filter Macro for Comparing Countries Sheet
' This macro automatically hides/shows country rows based on the region filter selection in cell E2.

Private Sub Worksheet_Change(ByVal Target As Range)
    If Not Intersect(Target, Range("E2")) Is Nothing Then
        Call FilterByRegion
    End If
End Sub

Private Sub FilterByRegion()
    Dim regionFilter As String
    Dim lastRow As Long
    Dim i As Long
    Dim cellRegion As String
    
    ' Get selected region from E2
    regionFilter = Range("E2").Value
    lastRow = Cells(Rows.Count, "A").End(xlUp).Row
    
    ' Show all rows first (row 5 onwards, row 4 is header)
    For i = 5 To lastRow
        Rows(i).Hidden = False
    Next i
    
    ' If ALL selected, show all
    If regionFilter = "ALL" Then Exit Sub
    
    ' Hide rows that don't match selected region (region is in column Z)
    For i = 5 To lastRow
        cellRegion = Cells(i, "Z").Value
        If cellRegion <> regionFilter Then
            Rows(i).Hidden = True
        End If
    Next i
End Sub
