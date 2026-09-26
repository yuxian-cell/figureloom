Sub Main

'Create Grapher as an Object
Dim Grapher As Object

'Start Grapher
Set Grapher = CreateObject("Grapher.Application")

Grapher.Visible = True

'Create a new document window
Set resultgrf_doc = Grapher.Documents.Add(grfPlotDoc)

resultgrf_doc.Windows.Item(1).PageUnits(grfInches)

resultgrf_doc.PageSetup.Width = 8.5
resultgrf_doc.PageSetup.Height = 11

'Define object pointer
Set Graph1_obj = resultgrf_doc.Shapes.Item(1)

'Define object pointer
Set LineScatterPlot_obj = Graph1_obj.Plots.Item(1)

'Call AddFit
LineScatterPlot_obj.AddFit(grfLinearFit)

End Sub
