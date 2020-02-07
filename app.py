external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
app.layout = html.Div(children=[
    html.Div(id='quote_table'),
    
    dcc.Interval(
        id='interval-component',
        interval=5000,
        n_intervals=1
    ),
    
])
@app.callback(
    Output('quote_table', 'children'),
    [Input('interval-component', 'n_intervals')])
def table(interval_component):
    
    fugle.update_data()
    
    return html.Div([
        
        fugle.message_table()
        
    ])
if __name__ == '__main__':
    app.run_server()