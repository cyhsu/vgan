import os
import re
import json
import requests 
import numpy as np
import pandas as pd
import xarray as xr
import cmocean as cmo
import dask.array as da
import ipywidgets as widgets
import bqplot.pyplot as bplt
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from glob import glob
from dask.distributed import Client
from IPython.display import display
from ipyleaflet.velocity import Velocity
from ipywidgets.embed import embed_minimal_html
from ipyleaflet import Map, basemaps, Polyline, AwesomeIcon, Marker
from bqplot import LinearScale, DateScale, ColorScale, HeatMap, GridHeatMap, Figure, LinearScale, OrdinalScale, Axis

#--- Only Useful in Jupyter Notebook/Lab
from IPython.core.interactiveshell import InteractiveShell
InteractiveShell.ast_node_interactivity = 'all'


def saveHTML(fid, url='https://gliders.ioos.us/erddap/tabledap/index.html'):
    with open(fid,'w') as f:
        f.write(requests.get(url).text)

def getMissionList(fid):
    mission_list = []
    for line in open(fid,'r'):
        if re.search('(tabledap)+(.*graph.*)',line) and (not re.search('delay', line)):
            mission_list.append(line.split('tabledap/')[1].split('.graph')[0])
    return mission_list[1:]    

def getJson(fid):
    try:
        with open(fid,'r') as f:
            return json.load(f)
    except:
        return {}

def saveJson(Json, fid):
    with open(fid,'w') as f:
        json.dump(Json, f)
        
def getMETA4PI(fid):
    ''' get Metadata for PI'''

    PIinfo = getJson('PIinfo.json')
    for row in getJson(fid)['table']['rows']:
        if 'contributor_name' in row: contributor = row[-1]
        elif 'contributor_role' in row: contributor_role = row[-1]
        elif 'deployment' in row: glider_mission = row[-1]
        elif 'time_coverage_start' in row: Date_Created = row[-1]
        elif 'time_coverage_end' in row: Date_Updated = row[-1]
        elif 'geospatial_lat_max' in row: lat_max = float(row[-1])
        elif 'geospatial_lat_min' in row: lat_min = float(row[-1])
        elif 'geospatial_lon_max' in row: lon_max = float(row[-1])
        elif 'geospatial_lon_min' in row: lon_min = float(row[-1])

    if (lat_max > 32.) or (lat_min < 18.) or (lon_max > -77) or (lon_min < -100):
        os.system('rm {}'.format(fid))
        return {'Status': 'OutOfDomain'}

    
    #-- Check PI's name
    if 'PI' in contributor_role: 
        contributor_role = contributor_role.replace('PI',
                                                    'Principal Investigator')
        
    if len(contributor_role.split(',')) == 1 and contributor_role == 'GCOOS Data Manager':
        PI = 'Matthew Howard'
    elif 'Naval' in contributor:
        PI = 'John Kerfoot'
    elif len(contributor_role.split(',')) == 1 and contributor_role == 'additional data management':
        PI = 'Bob Simons'
    else:
        PI = [contributor.split(',')[num] 
              for num, role in enumerate(contributor_role.split(',')) 
              if 'Principal Investigator' in role][0]
    try: 
        Institute = PIinfo[PI]['Institute']
    except: 
        Institute = 'Others'
    return {
        'PI': PI, 
        'Institute': Institute,
        'Time Coverage Start': Date_Created, 
        'Time Coverage End': Date_Updated,
        'Data Path': './Data/Glider/{}/{}'.format(Institute,fid[:-5]),
        'LOGO Path': PIinfo[PI]['logo_path'],
        'Status': 'Active'
    }

# @classmethod
def resumeMissionStatus(days=3):
    '''
        resume Glider Mission Status X days ago.
        X <- days. Default is 3 days before now.
    '''
    mission_status = getJson('mission_status.json')
    for mission in mission_status:
        if not mission_status['status'] == 'OutofDomain':
            TimeCoverageEnd = np.datetime64(mission_status[mission]['Time Coverage End'][:-1])
            TimeBound = np.datetime64('now') - np.timedelta64(days,'D')
            if TimeCoverageEnd >= TimeBound:
                mission_status[mission]['Status'] = 'Active'
                print(mission)
    saveJson(mission_status, 'mission_status.json')

# @classmethod
def checkGDAC(mission_list):
    ''' Check whether there is any new glider mission/data within the domain '''
    parameters = getJson('VGANparas.json')
    mission_status = getJson('mission_status.json')
    for mission in mission_list:    
        mission_file = '{}.json'.format(mission)
        if (mission not in mission_status.keys()) or (mission_status[mission]['Status'] == 'Active'):
            saveHTML(mission_file,url=parameters['GliderHeaderURL'].format(mission))
            meta = getMETA4PI(mission_file)
            mission_status[mission] = meta
    saveJson(mission_status, 'mission_status.json')
    
# @classmethod
def updateMission(mission_list):
    mission_status = getJson('mission_status.json')
    for mission in mission_status.keys():
        if mission_status[mission]['Status'] == 'Active':
            print('Active: ', mission)
            dirc = mission_status[mission]['Data Path']
            MissionEndTime = np.datetime64(mission_status[mission]['Time Coverage End'].replace('Z',''))
            TimeBound = np.datetime64('now') - np.timedelta64(3,'D')
            
            if not os.path.isdir(dirc): 
                os.system('mkdir -p "{}"'.format(dirc))

            saveHTML(mission,url='https://gliders.ioos.us/erddap/tabledap/{}.csv'.format(mission))                            
            os.system('mv {} {}.json "{}"/.'.format(mission, mission, dirc))
            if MissionEndTime < TimeBound: 
                mission_status[mission]['Status'] = 'Inactive'
    saveJson(mission_status,'mission_status.json')    

#### @classmethod
###def updateMission(mission_list):
###    mission_status = getJson('mission_status.json')
###    for mission in mission_status.keys():
###        status = mission_status[mission]['Status']
###        MissionEndTime = np.datetime64(mission_status[mission]['Time Coverage End'].replace('Z',''))
###        TimeBound = np.datetime64('now') - np.timedelta64(2,'D')
###
###        if MissionEndTime < TimeBound: 
###            status = 'Inactive'
###            mission_status[mission]['Status'] = status
###
###        if status == 'Active':
###            dirc = mission_status[mission]['Data Path']
###            print('Active: ', mission, MissionEndTime)
###            
###            if not os.path.isdir(dirc): 
###                os.system('mkdir -p "{}"'.format(dirc))
###
###            saveHTML(mission,url='https://gliders.ioos.us/erddap/tabledap/{}.csv'.format(mission))                            
###            os.system('mv {} {}.json "{}"/.'.format(mission, mission, dirc))
###    saveJson(mission_status,'mission_status.json')    


# @classmethod    
def getGliderData(DataPath):
    ''' DataPath: location of glider data on csv format from GDAC'''
    df = pd.read_csv(DataPath, sep=',', header=[0,1],dtype={'time_uv':str})
    df.columns = df.columns.droplevel(1)
    df['time'] = pd.to_datetime(df['time']).dt.tz_localize(None)
    df['depth']= df['depth'] * -1.
    df = df.dropna(subset=['depth'])
    return df
    
# @classmethod    
def PIcontribution(PI):
    mission, mission_status = [], getJson('mission_status.json')
    for key in mission_status.keys():
        if len(mission_status[key]) > 1 and mission_status[key]['PI'] == PI:
            try:
                df = getGliderData(mission_status[key]['Data Path']+'/{}'.format(key))
                mission.append(df.set_index('time').resample('D').count().trajectory)
                keys.append(key)            
            except:
                pass
    if not os.path.isdir('./Data/PIcontribution'): os.system('mkdir -p ./Data/PIcontribution')
    df = pd.concat(mission).to_frame().resample('D').sum()
    reindex = pd.date_range(start=str(df.index.year.min()),
                        end=str(df.index.year.max()+1),
                        freq='D')
    OutFile = './Data/PIcontribution/{}.json'.format(PI)
    if os.path.isfile(OutFile): os.system("rm '{}'".format(OutFile))
    df.reindex(reindex).to_json(OutFile)
    return print("PI ({})'s Contribution is calculated!".format(PI))    

# @classmethod    
def checkDownloadList():
    mission_status = getJson('mission_status.json')
    return [key for key in mission_status if mission_status[key]['Status'] == 'Active']

# @classmethod 
def checkModelDownloadPeriod(missions):
    ''' input <- checkDownload, output -> [1st-time - 12h, now]
    '''
    mission, mission_status = [], getJson('mission_status.json')
    for key in missions:
        df = getGliderData(mission_status[key]['Data Path']+'/{}'.format(key))
        mission.append(df.set_index('time').resample('D').count().trajectory)
    return [np.datetime64(pd.concat(mission).to_frame().index.min(),'D') - np.timedelta64(12,'h'), 
            np.datetime64('now','h')]

# @classmethod 
def downloadHYCOM_FTP(DatePeriod):
    ''' DatePeriod <- checkModelDownloadPeriod, (list, np.datetime64)'''
    url = 'ftp://ftp.hycom.org/datasets/GOMu0.04/expt_90.1m000/data/hindcasts/{}/{}'
    dirc, timedelta = './Data/Model/HYCOM/', np.timedelta64(1,'h')
    if not os.path.isdir(dirc): os.system('mkdir -p {}'.format(dirc))    
    for tid in range(*np.diff(DatePeriod).astype('int')):
        datetime = DatePeriod[0] + tid * timedelta
        year = datetime.astype('datetime64[Y]')
        date = datetime.astype('datetime64[D]')
        hour = (datetime - date).astype('int')
        if hour >= 12:
            date, hour = str(date), 't{:03d}'.format(hour - 12)
        else: 
            date, hour = str(date - np.timedelta64(1,'D')), 't{:03d}'.format(hour + 12)
        FileHead= 'hycom_gomu_901m000_'
        FTPfile = '{}{}12_{}.nc'.format(FileHead,date.replace('-',''),hour)
        OutFile = '{}{}{}.nc'.format(dirc,FileHead,datetime.astype('datetime64[h]'))
        DWLink  = url.format(year,FTPfile)
        if not os.path.isfile(OutFile):
            _ = os.system('wget -O {} -q {}'.format(OutFile, DWLink))
        _ = os.system('ls -l |grep "0B" | rev | cut -d " " -f 1 |rev | while read line; do rm -rf $line; done')
    
# @classmethod 
def getHYCOM_OPeNDAP():
    time_delta = np.timedelta64(1,'h')
    time_ref = np.datetime64('2000-01-01','h')
    url = 'https://tds.hycom.org/thredds/dodsC/GOMu0.04/expt_90.1m000'
    dh = xr.open_dataset(url, decode_times=False)
    dh['time'] = np.round(dh['time'].data) * time_delta + time_ref
    dh['depth']= -1.* dh['depth']
    return dh    

# @classmethod 
def getHYCOM_Local(HYCOMPath='./Data/Model/HYCOM/*.nc'):
    time_delta = np.timedelta64(1,'h')
    time_ref = np.datetime64('2000-01-01','h')
    dh = xr.open_mfdataset(HYCOMPath, decode_times=False)
    dh['time'] = np.round(dh['time'].data) * time_delta + time_ref
    dh['depth']= -1.* dh['depth']
    return dh

def computeHYCOM_Comparison(MissionList):
    ''' Compute HYCOM -> Glider, save with {mission dirc}/HYCOM_Comparison.nc'''
    dh = getHYCOM_Local()
    dh = dh[['water_temp', 'salinity']]
    mission_status = getJson('mission_status.json')
    for mission in MissionList:
        DataPath = mission_status[mission]['Data Path']+'/{}'.format(mission)
        dd = getGliderData(DataPath)
        lat, lon, tim, dep = dd[['latitude','longitude','time','depth']].values.T
        dhi = dh.sel(lat=slice(lat.min()-0.1,lat.max()+0.1), 
                     lon=slice(lon.min()-0.1,lon.max()+0.1)).load()

        lat = xr.DataArray(lat.astype('float32'),dims='profile').chunk(200)
        lon = xr.DataArray(lon.astype('float32'),dims='profile').chunk(200)
        dep = xr.DataArray(dep.astype('float32'),dims='profile').chunk(200)
        tim = xr.DataArray(tim,dims='profile').chunk(200)  

        OutFile = '{}/HYCOM_Comparison.nc'.format(mission_status[mission]['Data Path'])
        if os.path.isfile(OutFile): os.system('rm {}'.format(OutFile))
        dhii = dhi.interp(lon=lon,lat=lat,depth=dep,time=tim).to_netcdf(OutFile)

#-- About Plot.
def imageLogo(path="static/img/logo/GCOOS/GCOOS icon 01 colors no BG.png", 
              Layout = widgets.Layout(width = '100px',height = '100px', border = '2px solid black',margin = '1% 1% 1% 1%')):
    image = widgets.Image(value = open(path, "rb").read(), format='png', 
                          layout=widgets.Layout(object_fit = 'contain'))
    return widgets.Box([image], layout = Layout)

def headerTitle(headerLogo, 
                AppName='<h1> V-Gan </h1>',
                ExpName='<h3> The Visualization of Glider Dashboard </h3>', 
                GANDALF = '<a href="https://gandalf.gcoos.org"> GANDALF </a>',
                About   = '<a href=""> About </a>',
                Support = '<a href=""> Support </a>'):

    #--- Dark background + white text
    title_bg = widgets.HTML('<style>.title_bg{width:auto; background-color:black; color: #ffffff;}<style>')
    box_style = widgets.HTML('.box_style{width:40%; border : None; height: auto; background-color:black; color=white;}<style>')
    # title01.add_class('title_bg'); title02.add_class('title_bg')
    # html_title.add_class('box_style')

    title01 = widgets.HTML(AppName, layout=widgets.Layout(align_content='stretch', margin='1% 1% 1% 2% ', width='15%'))
    title02 = widgets.HTML(ExpName, layout=widgets.Layout(align_content='stretch', align_items = 'center', margin='1% 1% 1% -4%',width='60%'))
    link1, link2, link3 = widgets.HTML(GANDALF), widgets.HTML(About), widgets.HTML(Support)
    RightTitle = widgets.HBox([link1,link2,link3], layout = widgets.Layout(align_items='flex-end', justify_content='space-around',))
    
    title02 = widgets.VBox([title02, RightTitle], layout=widgets.Layout(width='100%'))
    title01 = widgets.HBox([title01, title02], layout=widgets.Layout(width='100%', align_items = 'center'))
    
    return widgets.HBox([headerLogo, title01], layout=widgets.Layout(margin='1% 1% 0% 7%', width='auto'))

def sidebarMissionHTML(ExpName, Name):
    return widgets.VBox([widgets.HTML(value = '<b><u>{}</u></b>'.format(ExpName)),
                         widgets.HTML(value = '<p>{}</p>'.format(Name))],
                        layout = widgets.Layout(align_items = 'center',justify_content = 'center', width='auto'))

def sidebarMissionInfo(mission, PI, TimeCoverageStart, TimeCoverageEnd):
    MissionName = sidebarMissionHTML('Glider Mission', mission)
    MissionPI = sidebarMissionHTML('PI',PI)
    MissionPeriod = sidebarMissionHTML('Date Period', '{} <br><br> {}'.format(TimeCoverageStart, TimeCoverageEnd))
    return MissionName, MissionPI, MissionPeriod


def sidebarCalendarHeatmap(PI):
    dataframe = pd.read_json('./Data/PIcontribution/{}.json'.format(PI))
    figs, years = [], np.unique(dataframe.index.year)

    #-- Calendar Heatmap by bqplot.
    for year in years[:-1]: #-- years[:-1] is because the end year + 1 is the upper bound.
        data = dataframe[str(year)]
        data = pd.DataFrame({'data':data.trajectory,'fill': 1,'day':data.index.dayofweek,'week':data.index.isocalendar().week})
        data.loc[(data.index.month ==  1) & (data.week > 50), 'week'] = 0
        data.loc[(data.index.month == 12) & (data.week < 10), 'week'] = data.week.max() + 1
        
        fill_data = data.pivot('day', 'week', 'fill').values[::-1]
        fill_data = np.ma.masked_where(np.isnan(fill_data), fill_data)
    
        plot_data = data.pivot('day','week','data').values#[::-1]
        plot_data = np.ma.masked_where(np.isnan(plot_data), plot_data)

        monthlabels=np.arange(data.index[0],data.index[-1]+np.timedelta64(1,'D'),dtype='datetime64[D]')[::7]
        daylabels=list(['Mon','Tue','Wed','Thr','Fri','Sat','Sun'])
    
        Layout = widgets.Layout(width='auto',height='200px')
        #Layout = widgets.Layout(width='100%',height='200px')
        fig = bplt.figure(layout=Layout,fig_margin=dict(top=20, bottom=20, left=60, right=40),padding_y=0,)

        xmin, xmax = np.datetime64('{:04d}-01-01'.format(year)), np.datetime64('{:04d}-12-31'.format(year))
        bplt.scales(scales={'x': DateScale(min=xmin,max=xmax,offset={'value':1},), 
                            'y': OrdinalScale(reverse=True)})   
        bplt.gridheatmap(fill_data,row=daylabels,column=monthlabels,stroke='white',opacity = 0.3,
                         scales={'color': ColorScale(scheme='Grays')},axes_options={'color': {'visible': False}})

        grid_map = bplt.gridheatmap(plot_data, row = daylabels,column = monthlabels,opacity = 0.7, stroke = 'white', 
                                    scales = {'color': ColorScale(colors=['whitesmoke', 'darkgreen'])},
                                    axes_options={'row':{'label_offset':'3em','label':str(year),'num_ticks':4,'grid_lines': 'none'},
                                                  'column':{'num_ticks':5,'grid_lines': 'none'},
                                                  'color':{'visible': False}})
        figs.append(fig)
    return widgets.VBox(figs,layout= widgets.Layout(align_items = 'center',justify_content = 'center',margin='2%',))

def scatter(ax,df,var,title='Glider',vmin=20,vmax=28,cmap=cmo.cm.thermal):
    coordinates = dict(x='time',y='depth',vmin=vmin,vmax=vmax,)
    if isinstance(df, pd.DataFrame):
        color= dict(c=var, colorbar=False, colormap=cmap)
    else:
        var = 'water_temp' if var == 'temperature' else var
        color= dict(hue=var, cmap=cmap, cbar_kwargs=dict(orientation='vertical', pad=0.01, shrink=1))
    coordinates.update(color)
    im = df.plot.scatter(**coordinates, ax=ax)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'));
    ax.set_xlabel('Date', fontsize=14)  
    ax.set_ylabel('Depth (m)', fontsize=14)
    ax.set_title(title, fontsize=14);
    ax.tick_params('both', labelsize=12)
    return coordinates, im
  
def plotHYCOM_Comparison(mission):
    mission_status = getJson('mission_status.json')
    DataPath = mission_status[mission]['Data Path']
    dd = getGliderData(DataPath+'/{}'.format(mission))#.set_index('time')
    dd = dd[['time','longitude','latitude','depth','pressure','temperature', 'conductivity','salinity']]
    df = xr.open_dataset(DataPath+'/HYCOM_Comparison.nc')
    
    Layout = widgets.Layout(justify_content='center',margin='1%',height='auto')
    outs = []
    for var in ['temperature', 'salinity']:
        if var == 'temperature':
            vrange = dict(vmin=10.0, vmax= 31.0, cmap=cmo.cm.thermal)
            clabel = 'Temperature ($^{\circ}$C)'
        else:
            vrange = dict(vmin=34.3, vmax= 36.8, cmap=cmo.cm.haline)
            clabel = 'Salinity'            

        fig, ax = plt.subplots(ncols=2, nrows=1, figsize=(14,6), constrained_layout=True)

        fig.canvas.toolbar_position = 'bottom'
        co0,im0 = scatter(ax.flat[0], dd, var=var, title='Glider', **vrange)
        co1,im1 = scatter(ax.flat[1], df, var=var, title='HYCOM GoM', **vrange)
        im1.colorbar.set_label(label=clabel, size='large', weight='bold')
        
        output = widgets.Output(layout=Layout)
        with output:
            display(fig)

        outs.append(widgets.Box([output]))
    tab = widgets.Tab(outs)
    tab.set_title(0, 'Seawater Temperature deg-C')
    tab.set_title(1, 'Seawater Salinity')
    tab.layout.height='auto'
    return tab

#----- Leaflet
def createLeafletMap(center = [26.3, -89.9], zoom=6):
    m = Map(basemap=basemaps.CartoDB.DarkMatter,
            center = center,
            zoom = zoom,
            interpolation='nearest')
    return m

def createLeafletMarker(m, mission, MapGliderLocation, popup=None):
    icon1 = AwesomeIcon(name='paper-plane-o',marker_color='red',icono_color='black',
                        icon_size=(2,2),spin=False)

    marker = Marker(icon=icon1,name = mission,
                    location = (MapGliderLocation[-1][0],MapGliderLocation[-1][1]-0.001),
                    draggable=False,opacity=0.3,rise_on_hover=True,)
    if popup:
        marker.popup = widgets.HTML('<h1><u>{}</u></h1>'.format(mission))
    m.add_layer(marker)
    return m
    
def createLeafletPolyline(m, MapGliderLocation, color='green'):
    lines = Polyline(locations=MapGliderLocation,color=color,weight=2,
                     stroke=True,opacity=1,line_cap='butt',fill=False)
    m.add_layer(lines)
    return m

def createLeafletVelocity(m, dh):
    display_options = {'velocityType':'GoM Water Current',
                       'displayPosition':'bottomleft',
                       'displayEmptyString':'No Water Current data',}
    vel = Velocity(data=dh,
                   zonal_speed='water_u',
                   meridional_speed='water_v',
                   latitude_dimension='lat',
                   longitude_dimension='lon',
                   velocity_scale=0.1,
                   max_velocity=1.0,
                   display_options=display_options)

    m. add_layer(vel)
    return m

#----- Data Visualization App.
def view(mission, dh, OutHtmlPath=None):
    '''
         mission <- glider mission name, by GDAC
         OutHtmlPath <- html path, default is the data path of mission
                        please provide the full path with index.html (or name it).
    '''
    MissionList = checkDownloadList()
    mission_status = getJson('mission_status.json')
    PI = mission_status[mission]['PI']
    TimeCoverageStart = mission_status[mission]['Time Coverage Start']
    TimeCoverageEnd = mission_status[mission]['Time Coverage End']

    print(mission_status[mission])
    print(mission, PI, TimeCoverageStart, TimeCoverageEnd)
    #--- GCOOS logo & HTML header setup.
    headerLogo = imageLogo()
    header = headerTitle(headerLogo)
    
    Layout = widgets.Layout(width = '150px', height = '150px', border = '2px',
                            align_items = 'center', justify_content = 'center', margin='2%', )
    SidebarLogo = imageLogo(path=mission_status[mission]['LOGO Path'], Layout = Layout)
    MissionName, MissionPI, MissionPeriod = sidebarMissionInfo(mission, PI, TimeCoverageStart, TimeCoverageEnd)
    PIcontribution = sidebarCalendarHeatmap(PI)
    LeftSidebar = widgets.VBox([SidebarLogo, MissionName, MissionPI, MissionPeriod, PIcontribution],
                               layout = widgets.Layout(flex_flow='column',align_items = 'center', margin= '1%',
                                                       justify_content='space-around',width='auto',height='auto'))
    RightLowerFigure = plotHYCOM_Comparison(mission)
    
    Lmap = createLeafletMap()
    for mi in MissionList:
        MarkerPopup, DataPath = None, mission_status[mi]['Data Path']
        dd = getGliderData(DataPath+'/{}'.format(mi))[['time','longitude','latitude']]
        lon, lat, tim= dd.longitude.unique(), dd.latitude.unique(), dd.time.values
        MapGliderLocation = [[a,b] for (a,b) in zip(lat,lon)]
    
        Lmap = createLeafletPolyline(Lmap, MapGliderLocation)
        if mission == mi: 
            MarkerPopup = True
            Lmap = createLeafletPolyline(Lmap, MapGliderLocation, color='white')
        Lmap = createLeafletMarker(Lmap, mi, MapGliderLocation, MarkerPopup)
        
    Lmap = createLeafletVelocity(Lmap, dh.isel(time=-1,depth=0))
    
    Layout = widgets.Layout(flex_flow='column',justify_content='center',margin='1%')
    center = widgets.VBox([Lmap, RightLowerFigure], layout=Layout)
    center = widgets.HBox([LeftSidebar, center])
    app = widgets.VBox([header, center])

    OutHtmlPath = OutHtmlPath if OutHtmlPath else mission_status[mission]['Data Path']+'/{}.html'.format(mission)
    embed_minimal_html(OutHtmlPath, 
                       views=[app], title = '{} Widgets'.format(mission))
    return app



if __name__ == '__main__':

   #--- Loading Parameters. 
	PIinfo = getJson('PIinfo.json')
	parameters = getJson('VGANparas.json')
###
###	#--- Download Glider Mission List from GDAC
###	saveHTML('index.html',url='https://gliders.ioos.us/erddap/tabledap/index.html')
###
###	#--- Extract the mission items
###	mission_list = getMissionList('index.html')
###
###	#--- Check whether there is any mission in "Active" status
###	checkGDAC(mission_list)
###
###	#--- Update the Mission Status for "Active" missions
###	updateMission(mission_list)
###
###	#--- Reload and restore the  "Active" missions data
###	MissionList = checkDownloadList()

	#--- Calculate the PI's contribution
	for PI in PIinfo.keys():
		PIcontribution(PI)

	#--- Extract the earliest/latest datetime from "Active" missions
	DatePeriod = checkModelDownloadPeriod(MissionList)

###	#--- Download the HYCOM Hindcast Model outputs, and Interpolate the model output into glider position (lon/lat/time)
###	downloadHYCOM_FTP(DatePeriod)
###	if len(MissionList) > 0: computeHYCOM_Comparison(MissionList)
