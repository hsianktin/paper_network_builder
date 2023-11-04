#!/usr/bin/env python3
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import requests
import json
import time
# use argparse to get the query
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("query", help="the query to search")
args = parser.parse_args()
query = args.query

def search_semantic_scholar(query):
    result_limit = 40
    rsp = requests.get('https://api.semanticscholar.org/graph/v1/paper/search',
                        params={'query': query, 'limit': result_limit, 'fields': 'title,externalIds,year'})
    rsp.raise_for_status()
    results = rsp.json()
    total = results["total"]
    data = results["data"]

    DOIS = []
    for i in range(0,len(data)):
        # check if DOI exists
        if 'DOI' in data[i]['externalIds']:
            DOIS.append(data[i]['externalIds']['DOI'])
        else:
            DOIS.append('')

    # convert list data to dataframe
    df = pd.DataFrame(data)
    # insert DOIs
    df.insert(2,'DOI',DOIS)
    # remove unnecessary columns on externalIds
    df.drop(['externalIds'],axis=1,inplace=True)
    df.to_csv("data/"+query+'_search_results.csv')
    return df

def get_citation(paper_id):
    rsp = requests.get('https://api.semanticscholar.org/graph/v1/paper/'+paper_id+'/citations',
                        params={'fields': 'title,externalIds,year'})
    rsp.raise_for_status() 
    # the intent of raise_for_status() is to raise an exception if the request response was unsuccessful
    results = rsp.json()
    data = results['data']
    citing_papers = []
    for i in range(0,len(data)):
        citing_papers.append(data[i]['citingPaper'])
    DOIS = []
    for i in range(0,len(citing_papers)):
        # check if DOI exists
        if 'DOI' in citing_papers[i]['externalIds']:
            DOIS.append(citing_papers[i]['externalIds']['DOI'])
        else:
            DOIS.append('')
    df_citing_papers = pd.DataFrame(citing_papers)
    df_citing_papers.insert(2,'DOI',DOIS)
    df_citing_papers.drop(['externalIds'],axis=1,inplace=True)
    return df_citing_papers

def get_reference(paper_id):
    rsp = requests.get('https://api.semanticscholar.org/graph/v1/paper/'+paper_id+'/references',
                        params={'fields': 'title,externalIds,year'})
    rsp.raise_for_status() 
    # the intent of raise_for_status() is to raise an exception if the request response was unsuccessful
    results = rsp.json()
    data = results['data']
    cited_papers = []
    for i in range(0,len(data)):
        cited_papers.append(data[i]['citedPaper'])
    DOIS = []
    for i in range(0,len(cited_papers)):
        # check if DOI exists
        if cited_papers[i]['externalIds'] is not None:
            if 'DOI' in cited_papers[i]['externalIds']:
                DOIS.append(cited_papers[i]['externalIds']['DOI'])
            else:
                DOIS.append('')
        else:
            DOIS.append('')
    df_cited_papers = pd.DataFrame(cited_papers)
    df_cited_papers.insert(0,'DOI',DOIS)
    # df_cited_papers.drop(['externalIds'],axis=1,inplace=True)
    return df_cited_papers

df = search_semantic_scholar(query)

lists_cited_paper = []
for i in range(0,len(df)):
    lists_cited_paper.append(get_reference(df['paperId'][i]))
    time.sleep(0.1)

paper_network = nx.DiGraph()
# initialize the paper network
for i in range(0,len(df)):
    if df['paperId'][i] is not None:
        paper_network.add_node(df['paperId'][i],label=df['title'][i],date=str(df['year'][i]),time_stamp = df['year'][i], doi=df['DOI'][i])

# build the paper network by investigating the references of each paper using lists_cited_paper
for i in range(0,len(df)):
    df_cited_papers = lists_cited_paper[i]
    paper_citing = df['paperId'][i]
    for j in range(0,len(df_cited_papers)):
        paper_being_cited = df_cited_papers['paperId'][j]
        # if paper_citing is already in the paper_network, add an edge
        if paper_being_cited is not None:
            if not paper_network.has_node(paper_being_cited):
                paper_network.add_node(paper_being_cited,label=df_cited_papers['title'][j],date=str(df_cited_papers['year'][j]),time_stamp = df_cited_papers['year'][j], doi=df_cited_papers['DOI'][j])
            # the edge is from paper_citing to paper_being_cited
            paper_network.add_edge(paper_citing,paper_being_cited)
# # iterate through the paper_network to add edges
import tqdm
print("extending the paper network by investigating the additional references of each paper")
for i in tqdm.tqdm(range(0,len(paper_network.nodes))):
    paper_id = list(paper_network.nodes)[i]
    paper_citing = paper_id
    # skip the following if paper_id is None or is present in df
    if paper_id is None or paper_id in df['paperId']:
        continue
    df_cited_papers = get_reference(paper_id)
    if len(df_cited_papers.keys()) <= 1:
        continue
    for j in range(0,len(df_cited_papers)):
        paper_cited = df_cited_papers['paperId'][j]
        # if paper_citing is already in the paper_network, add an edge
        if paper_network.has_node(paper_cited):
            paper_network.add_edge(paper_citing,paper_cited)
        else:
            if paper_cited is not None:
                paper_network.add_node(paper_cited,label=df_cited_papers['title'][j],date=str(df_cited_papers['year'][j]),time_stamp = df_cited_papers['year'][j], doi=df_cited_papers['DOI'][j])
                paper_network.add_edge(paper_citing,paper_cited)
    time.sleep(0.5)

# remove quasi-isolated nodes (nodes with only one edge)
node_in_degree = dict(paper_network.in_degree)
# remove nodes with in_degree = 1
for node in node_in_degree:
    if node_in_degree[node] == 1 and node not in df['paperId']:
        paper_network.remove_node(node)

# if number of nodes > 1000 delete nodes with lowest total degrees

# save the paper network
nx.write_gexf(paper_network,"data/"+query+".gexf")
while len(paper_network.nodes) > 1000:
    node_degree = dict(paper_network.degree)
    node_degree_sorted = sorted(node_degree.items(), key=lambda x: x[1])
    paper_network.remove_node(node_degree_sorted[0][0])

from bokeh.io import output_file,output_notebook, show, save
from bokeh.models import Range1d, Circle, ColumnDataSource, MultiLine, NodesAndLinkedEdges, EdgesAndLinkedNodes, LabelSet, HoverTool, TapTool, OpenURL, BoxSelectTool
from bokeh.plotting import figure
from bokeh.plotting import from_networkx
from bokeh.palettes import Blues8, Reds8, Purples8, Oranges8, Viridis8, Spectral4
from bokeh.transform import linear_cmap
mapping = dict((n, i) for i, n in enumerate(paper_network.nodes))
H = nx.relabel_nodes(paper_network, mapping)

width = 800
height = 800
#Choose a title!
title = 'Paper network of ' + query
output_file("data/"+query+".html")
# process the network
cited_by = dict(H.in_degree)
nx.set_node_attributes(H,name='cited_by',values=cited_by)
degrees = dict(H.degree)
nx.set_node_attributes(H,name='degree',values=degrees)
size_by_this_attribute = 'degree'
color_by_this_attribute = 'time_stamp'

#Establish which categories will appear when hovering over each node
HOVER_TOOLTIPS = [("Paper", "@label"),("Cited-by Counts","@cited_by"),("Date","@date")]
color_palette = Blues8

#Create a plot — set dimensions, toolbar, and title
plot = figure(tools="pan,wheel_zoom,save,reset", active_scroll='wheel_zoom',
            x_range=Range1d(-10.1, 10.1), y_range=Range1d(-10.1, 10.1), 
            title=title, width=width, height=height)

plot.add_tools(HoverTool(tooltips = HOVER_TOOLTIPS), TapTool(), BoxSelectTool())
#Create a network graph object with spring layout
# https://networkx.github.io/documentation/networkx-1.9/reference/generated/networkx.drawing.layout.spring_layout.html
graph_renderer = from_networkx(H, nx.kamada_kawai_layout, scale=10, center=(0, 0))

#Set node size and color
minimum_value_color = min(graph_renderer.node_renderer.data_source.data[color_by_this_attribute])
maximum_value_color = max(graph_renderer.node_renderer.data_source.data[color_by_this_attribute])
graph_renderer.node_renderer.glyph = Circle(size=size_by_this_attribute, fill_color=linear_cmap(color_by_this_attribute, color_palette, minimum_value_color, maximum_value_color))
graph_renderer.node_renderer.selection_glyph = Circle(size=size_by_this_attribute, fill_color=Oranges8[2])
graph_renderer.node_renderer.hover_glyph = Circle(size=size_by_this_attribute, fill_color=Oranges8[1])

#Set edge opacity and width
graph_renderer.edge_renderer.glyph = MultiLine(line_alpha=0.5, line_width=1)
graph_renderer.edge_renderer.selection_glyph = MultiLine(line_alpha=0.5, line_width=5, line_color=Oranges8[2])
graph_renderer.edge_renderer.hover_glyph = MultiLine(line_alpha=0.5, line_width=5, line_color=Oranges8[1])


graph_renderer.selection_policy = NodesAndLinkedEdges()
graph_renderer.inspection_policy = NodesAndLinkedEdges()


# labels
pos = graph_renderer.layout_provider.graph_layout
x,y=zip(*pos.values())
graph_renderer.node_renderer.data_source.data['x']=x
graph_renderer.node_renderer.data_source.data['y']=y
label=LabelSet(x='x', y='y', text='label',level='glyph', source=graph_renderer.node_renderer.data_source)


# url by doi
url = "https://doi.org/@doi"
tap_tool = plot.select(type = TapTool)
tap_tool.callback = OpenURL(url=url)


#Add network graph to the plot

plot.renderers.append(graph_renderer)
# plot.renderers.append(label)
show(plot)
save(plot,"data/"+query+".html")

width = 800
height = 800
#Choose a title!
title = 'Paper network of ' + query
output_file("data/"+query+"_cited_by.html")
# process the network
cited_by = dict(H.in_degree)
nx.set_node_attributes(H,name='cited_by',values=cited_by)
degrees = dict(H.degree)
nx.set_node_attributes(H,name='degree',values=degrees)
size_by_this_attribute = 'cited_by'
color_by_this_attribute = 'time_stamp'

#Establish which categories will appear when hovering over each node
HOVER_TOOLTIPS = [("Paper", "@label"),("Cited-by Counts","@cited_by"),("Date","@date")]
color_palette = Blues8

#Create a plot — set dimensions, toolbar, and title
plot = figure(tools="pan,wheel_zoom,save,reset", active_scroll='wheel_zoom',
            x_range=Range1d(-10.1, 10.1), y_range=Range1d(-10.1, 10.1), 
            title=title, width=width, height=height)

plot.add_tools(HoverTool(tooltips = HOVER_TOOLTIPS), TapTool(), BoxSelectTool())
#Create a network graph object with spring layout
# https://networkx.github.io/documentation/networkx-1.9/reference/generated/networkx.drawing.layout.spring_layout.html
graph_renderer = from_networkx(H, nx.kamada_kawai_layout, scale=10, center=(0, 0))

#Set node size and color
minimum_value_color = min(graph_renderer.node_renderer.data_source.data[color_by_this_attribute])
maximum_value_color = max(graph_renderer.node_renderer.data_source.data[color_by_this_attribute])
graph_renderer.node_renderer.glyph = Circle(size=size_by_this_attribute, fill_color=linear_cmap(color_by_this_attribute, color_palette, minimum_value_color, maximum_value_color))
graph_renderer.node_renderer.selection_glyph = Circle(size=size_by_this_attribute, fill_color=Oranges8[2])
graph_renderer.node_renderer.hover_glyph = Circle(size=size_by_this_attribute, fill_color=Oranges8[1])

#Set edge opacity and width
graph_renderer.edge_renderer.glyph = MultiLine(line_alpha=0.5, line_width=1)
graph_renderer.edge_renderer.selection_glyph = MultiLine(line_alpha=0.5, line_width=5, line_color=Oranges8[2])
graph_renderer.edge_renderer.hover_glyph = MultiLine(line_alpha=0.5, line_width=5, line_color=Oranges8[1])


graph_renderer.selection_policy = NodesAndLinkedEdges()
graph_renderer.inspection_policy = NodesAndLinkedEdges()


# labels
pos = graph_renderer.layout_provider.graph_layout
x,y=zip(*pos.values())
graph_renderer.node_renderer.data_source.data['x']=x
graph_renderer.node_renderer.data_source.data['y']=y
label=LabelSet(x='x', y='y', text='label',level='glyph', source=graph_renderer.node_renderer.data_source)


# url by doi
url = "https://doi.org/@doi"
tap_tool = plot.select(type = TapTool)
tap_tool.callback = OpenURL(url=url)


#Add network graph to the plot

plot.renderers.append(graph_renderer)
# plot.renderers.append(label)
show(plot)
save(plot,"data/"+query+"_cited_by.html")

