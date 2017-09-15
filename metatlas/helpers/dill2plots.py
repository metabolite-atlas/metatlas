import sys
import os
import os.path
# os.environ['R_LIBS_USER'] = '/project/projectdirs/metatlas/r_pkgs/'
#curr_ld_lib_path = ''


from metatlas import metatlas_objects as metob
from metatlas import h5_query as h5q
from metatlas.helpers import metatlas_get_data_helper_fun as ma_data
from metatlas.helpers import spectralprocessing as sp
from metatlas import gui

from textwrap import fill, TextWrapper
import qgrid
import pandas as pd
import os
import tables
import pickle
import dill
import numpy as np
import re
import json
from matplotlib import pyplot as plt

from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors, AllChem, Draw, rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D, IPythonConsole
from itertools import cycle
from collections import defaultdict
from IPython.display import SVG,display


from ipywidgets import interact, interactive, fixed
import ipywidgets as widgets
from IPython.display import display

import getpass

from ast import literal_eval
# from datetime import datetime

from matplotlib.widgets import Slider, Button, RadioButtons

from matplotlib.widgets import AxesWidget

class VertSlider(AxesWidget):
    """
    A slider representing a floating point range

    The following attributes are defined
      *ax*        : the slider :class:`matplotlib.axes.Axes` instance

      *val*       : the current slider value

      *vline*     : a :class:`matplotlib.lines.Line2D` instance
                     representing the initial value of the slider

      *poly*      : A :class:`matplotlib.patches.Polygon` instance
                     which is the slider knob

      *valfmt*    : the format string for formatting the slider text

      *label*     : a :class:`matplotlib.text.Text` instance
                     for the slider label

      *closedmin* : whether the slider is closed on the minimum

      *closedmax* : whether the slider is closed on the maximum

      *slidermin* : another slider - if not *None*, this slider must be
                     greater than *slidermin*

      *slidermax* : another slider - if not *None*, this slider must be
                     less than *slidermax*

      *dragging*  : allow for mouse dragging on slider

    Call :meth:`on_changed` to connect to the slider event
    """
    def __init__(self, ax, label, valmin, valmax, valinit=0.5, valfmt='%.1e',
                 closedmin=True, closedmax=True, slidermin=None,
                 slidermax=None, dragging=True, **kwargs):
        """
        Create a slider from *valmin* to *valmax* in axes *ax*

        *valinit*
            The slider initial position

        *label*
            The slider label

        *valfmt*
            Used to format the slider value

        *closedmin* and *closedmax*
            Indicate whether the slider interval is closed

        *slidermin* and *slidermax*
            Used to constrain the value of this slider to the values
            of other sliders.

        additional kwargs are passed on to ``self.poly`` which is the
        :class:`matplotlib.patches.Rectangle` which draws the slider
        knob.  See the :class:`matplotlib.patches.Rectangle` documentation
        valid property names (e.g., *facecolor*, *edgecolor*, *alpha*, ...)
        """
        AxesWidget.__init__(self, ax)

        self.valmin = valmin
        self.valmax = valmax
        self.val = valinit
        self.valinit = valinit
        self.poly = ax.axhspan(valmin, valinit, 0, 1, **kwargs)

        self.vline = ax.axhline(valinit, 0, 1, color='r', lw=1)

        self.valfmt = valfmt
        ax.set_xticks([])
        ax.set_ylim((valmin, valmax))
        ax.set_yticks([])
        ax.set_navigate(False)

        self.connect_event('button_press_event', self._update)
        self.connect_event('button_release_event', self._update)
        if dragging:
            self.connect_event('motion_notify_event', self._update)
        self.label = ax.text(0.5, 1.03, label, transform=ax.transAxes,
                             verticalalignment='center',
                             horizontalalignment='center')

        self.valtext = ax.text(0.5, -0.03, valfmt % valinit,
                               transform=ax.transAxes,
                               verticalalignment='center',
                               horizontalalignment='center')

        self.cnt = 0
        self.observers = {}

        self.closedmin = closedmin
        self.closedmax = closedmax
        self.slidermin = slidermin
        self.slidermax = slidermax
        self.drag_active = False

    def _update(self, event):
        """update the slider position"""
        if self.ignore(event):
            return

        if event.button != 1:
            return

        if event.name == 'button_press_event' and event.inaxes == self.ax:
            self.drag_active = True
            event.canvas.grab_mouse(self.ax)

        if not self.drag_active:
            return

        elif ((event.name == 'button_release_event') or
              (event.name == 'button_press_event' and
               event.inaxes != self.ax)):
            self.drag_active = False
            event.canvas.release_mouse(self.ax)
            return

        val = event.ydata
        if val <= self.valmin:
            if not self.closedmin:
                return
            val = self.valmin
        elif val >= self.valmax:
            if not self.closedmax:
                return
            val = self.valmax

        if self.slidermin is not None and val <= self.slidermin.val:
            if not self.closedmin:
                return
            val = self.slidermin.val

        if self.slidermax is not None and val >= self.slidermax.val:
            if not self.closedmax:
                return
            val = self.slidermax.val

        self.set_val(val)

    def set_val(self, val):
        xy = self.poly.xy
        xy[1] = 0, val
        xy[2] = 1, val
        self.poly.xy = xy
        self.valtext.set_text(self.valfmt % val)
        if self.drawon:
            self.ax.figure.canvas.draw()
        self.val = val
        if not self.eventson:
            return
        for cid, func in self.observers.iteritems():
            func(val)

    def on_changed(self, func):
        """
        When the slider value is changed, call *func* with the new
        slider position

        A connection id is returned which can be used to disconnect
        """
        cid = self.cnt
        self.observers[cid] = func
        self.cnt += 1
        return cid

    def disconnect(self, cid):
        """remove the observer with connection id *cid*"""
        try:
            del self.observers[cid]
        except KeyError:
            pass

    def reset(self):
        """reset the slider to the initial value if needed"""
        if (self.val != self.valinit):
            self.set_val(self.valinit)


class adjust_rt_for_selected_compound(object):
    def __init__(self,
                 data,
                 include_lcmsruns = None, 
                 exclude_lcmsruns = None, 
                 include_groups = None, 
                 exclude_groups = None, 
                 compound_idx = 0,
                 width = 12,
                 height = 6,
                 y_scale='linear',
                 alpha = 0.5,
                 min_max_color = 'sage',
                 peak_color = 'darkviolet',
                 slider_color = 'ghostwhite',
                 y_max = 'auto',
                 y_min = 0):
        """
        data: a metatlas_dataset where files and compounds are stored.
        for example, 
        self.metatlas_dataset[file_idx][compound_idx]['identification'].rt_references[-1].unique_id
        is the unique id to the retention time reference for a compound in a file.
        
        width: specify a width value in inches for the plots and slides
        height: specify a width value in inches for the plots and slides
        min_max_color & peak_color: specify a valid matplotlib color string for the slider and vertical bars
        slider_color: background color for the sliders. Must be a valid matplotlib color

        Press Left and Right arrow keys to move to the next or previous compound
        """
        
        self.compound_idx = compound_idx
        self.width = width
        self.height = height
        self.y_scale = y_scale
        self.alpha = alpha
        self.min_max_color = min_max_color
        self.peak_color = peak_color
        self.slider_color = slider_color
        self.y_max = y_max
        self.y_min = y_min
        
        # filter runs from the metatlas dataset
        if include_lcmsruns:
            data = filter_lcmsruns_in_dataset_by_include_list(data,'lcmsrun',include_lcmsruns)
        
        if include_groups:
            data = filter_lcmsruns_in_dataset_by_include_list(data,'group',include_groups)
        if exclude_lcmsruns:
            data = filter_lcmsruns_in_dataset_by_exclude_list(data,'lcmsrun',exclude_lcmsruns)
        if exclude_groups:
            data = filter_lcmsruns_in_dataset_by_exclude_list(data,'group',exclude_groups)     
        self.data = data
        
        # create figure and first axes
        self.fig,self.ax = plt.subplots(figsize=(width, height))
        plt.subplots_adjust(left=0.09, bottom=0.275)
#         plt.ticklabel_format(style='plain', axis='x')
#         plt.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
        
        # warn the user if they do not own the atlas; and can not edit its values
        self.enable_edit = True
        self.atlas = metob.retrieve('Atlas',unique_id = self.data[0][0]['atlas_unique_id'],username='*')[-1]
        print("loaded file for username = ", self.atlas.username)
        if getpass.getuser() != self.atlas.username:
            self.ax.set_title("YOUR ARE %s YOU ARE NOT ALLOWED TO EDIT VALUES THE RT CORRECTOR. USERNAMES ARE NOT THE SAME"%getpass.getuser())
            self.enable_edit = False
            
        #create all event handlers
        self.fig.canvas.callbacks.connect('pick_event', self.on_pick)
        self.fig.canvas.mpl_connect('key_press_event', self.press)

        #create the plot
        self.set_plot_data()
        

    def set_plot_data(self):
        #set y-scale and bounds if provided
        self.ax.set_yscale(self.y_scale)
        if self.y_max != 'auto':
            self.ax.set_ylim(self.y_min,self.y_max)
            
        self.ax.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
        
        default_data = self.data[0][self.compound_idx]
        if default_data['identification'].name:
            compound_str = default_data['identification'].name.split('///')[0]
        elif default_data['identification'].compound[-1].name:
            compound_str = default_data['identification'].compound[-1].name
        else:
            compound_str = 'nameless compound'
            
        compound_str = '%d, %s'%(self.compound_idx, compound_str)
        
        self.ax.set_title('')
        self.ax.set_ylabel('%s'%compound_str)
        self.ax.set_xlabel('Retention Time')
        self.my_rt = metob.retrieve('RTReference',
                               unique_id = default_data['identification'].rt_references[-1].unique_id, username='*')[-1]
        for d in self.data: #this loops through the files
            if d[self.compound_idx]['data']['eic']:
                if len(d[self.compound_idx]['data']['eic']['rt']) > 0:
                    x = d[self.compound_idx]['data']['eic']['rt']
                    y = d[self.compound_idx]['data']['eic']['intensity']
                    x = np.asarray(x)
                    y = np.asarray(y)
                    minval = np.min(y[np.nonzero(y)])
                    y = y - minval
                    x = x[y>0]
                    y = y[y>0]#y[y<0.0] = 0.0
                    self.ax.plot(x,y,'k-',linewidth=2.0,alpha=self.alpha, picker=5, label = d[self.compound_idx]['lcmsrun'].name.replace('.mzML',''))
                    

        self.min_line = self.ax.axvline(self.my_rt.rt_min, color=self.min_max_color,linewidth=4.0)
        self.max_line = self.ax.axvline(self.my_rt.rt_max, color=self.min_max_color,linewidth=4.0)
        self.peak_line = self.ax.axvline(self.my_rt.rt_peak, color=self.peak_color,linewidth=4.0)
      
        self.rt_peak_ax = plt.axes([0.09, 0.05, 0.81, 0.03], axisbg=self.slider_color)
        self.rt_max_ax = plt.axes([0.09, 0.1, 0.81, 0.03], axisbg=self.slider_color)
        self.rt_min_ax = plt.axes([0.09, 0.15, 0.81, 0.03], axisbg=self.slider_color)

        self.y_scale_ax = plt.axes([0.925, 0.275, 0.02, 0.63], axisbg=self.slider_color)

        min_x = self.ax.get_xlim()[0]
        max_x = self.ax.get_xlim()[1]
        
        self.rt_min_slider = Slider(self.rt_min_ax, 'RT min', min_x, max_x, valinit=self.my_rt.rt_min,color=self.min_max_color)
        self.rt_min_slider.vline.set_color('black')
        self.rt_min_slider.vline.set_linewidth(4)
        self.rt_max_slider = Slider(self.rt_max_ax, 'RT max', min_x, max_x, valinit=self.my_rt.rt_max,color=self.min_max_color)
        self.rt_max_slider.vline.set_color('black')
        self.rt_max_slider.vline.set_linewidth(4)
        self.rt_peak_slider = Slider(self.rt_peak_ax,'RT peak', min_x, max_x, valinit=self.my_rt.rt_peak,color=self.peak_color)
        self.rt_peak_slider.vline.set_color('black')
        self.rt_peak_slider.vline.set_linewidth(4)
        if self.enable_edit:
            self.rt_min_slider.on_changed(self.update_rt)
            self.rt_max_slider.on_changed(self.update_rt)
            self.rt_peak_slider.on_changed(self.update_rt)



        (self.slider_y_min,self.slider_y_max) = self.ax.get_ylim()
        self.slider_val = self.slider_y_max            
        self.y_scale_slider = VertSlider(self.y_scale_ax,'',self.slider_y_min,self.slider_y_max, valfmt = '', valinit=self.slider_y_max,color=self.peak_color)
        self.y_scale_slider.vline.set_color('black')
        self.y_scale_slider.vline.set_linewidth(8)
        self.y_scale_slider.on_changed(self.update_yscale)
        
        self.lin_log_ax = plt.axes([0.1, 0.75, 0.1, 0.15])#, axisbg=axcolor)
        self.lin_log_ax.axis('off')
        self.lin_log_radio = RadioButtons(self.lin_log_ax, ('linear', 'log'))
        self.lin_log_radio.on_clicked(self.set_lin_log)

        self.peak_flag_ax = plt.axes([0.8, 0.75, 0.1, 0.15])#, axisbg=axcolor)
        self.peak_flag_ax.axis('off')
        peak_flags = ('keep', 'remove', 'check')
        my_id = metob.retrieve('CompoundIdentification',
                               unique_id = self.data[0][self.compound_idx]['identification'].unique_id, username='*')[-1]
        if my_id.description in peak_flags:
            peak_flag_index = peak_flags.index(my_id.description)
        else:
            peak_flag_index = 0
        self.peak_flag_radio = RadioButtons(self.peak_flag_ax, peak_flags)
        self.peak_flag_radio.on_clicked(self.set_peak_flag)
        self.peak_flag_radio.set_active(peak_flag_index)
        
    def set_lin_log(self,label):
        self.ax.set_yscale(label)
        self.ax.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
        self.fig.canvas.draw_idle()

    def set_peak_flag(self,label):
        my_id = metob.retrieve('CompoundIdentification',
                               unique_id = self.data[0][self.compound_idx]['identification'].unique_id, username='*')[-1]
        my_id.description = label
        metob.store(my_id)

    def on_pick(self,event):
        thisline = event.artist
        thisline.set_color('red')
        self.ax.set_title(thisline.get_label())        
    
    def press(self,event):
        if event.key == 'right':
            if self.compound_idx + 1 < len(self.data[0]):
                self.compound_idx += 1
                self.ax.cla()
                self.rt_peak_ax.cla()
                self.rt_min_ax.cla()
                self.rt_max_ax.cla()
                self.y_scale_ax.cla()
                self.set_plot_data()
        if event.key == 'left':
            if self.compound_idx > 0:
                self.compound_idx -= 1
                self.ax.cla()
                self.rt_peak_ax.cla()
                self.rt_min_ax.cla()
                self.rt_max_ax.cla()
                self.y_scale_ax.cla()
                self.set_plot_data()
        if event.key == 'x':
            self.peak_flag_radio.set_active(1)
            #This is really hacky, but using set_peak_flag function above didn't work.
            my_id = metob.retrieve('CompoundIdentification',
                               unique_id = self.data[0][self.compound_idx]['identification'].unique_id, username='*')[-1]
            my_id.description = 'remove'
            metob.store(my_id)            
        
    def update_yscale(self,val):
        self.y_scale_slider.valinit = self.slider_val
        self.slider_val = self.y_scale_slider.val
        self.ax.set_ylim(self.slider_y_min,self.slider_val)
        self.fig.canvas.draw_idle()
        
    def update_rt(self,val):
        self.my_rt.rt_min = self.rt_min_slider.val
        self.my_rt.rt_max = self.rt_max_slider.val
        self.my_rt.rt_peak = self.rt_peak_slider.val
        
        self.rt_min_slider.valinit = self.my_rt.rt_min
        self.rt_max_slider.valinit = self.my_rt.rt_max
        self.rt_peak_slider.valinit = self.my_rt.rt_peak
        
        metob.store(self.my_rt)
        self.min_line.set_xdata((self.my_rt.rt_min,self.my_rt.rt_min))
        self.max_line.set_xdata((self.my_rt.rt_max,self.my_rt.rt_max))
        self.peak_line.set_xdata((self.my_rt.rt_peak,self.my_rt.rt_peak))
        self.fig.canvas.draw_idle()
        
class adjust_mz_for_selected_compound(object):
    def __init__(self,
                 data,
                 include_lcmsruns = None, 
                 exclude_lcmsruns = None, 
                 include_groups = None, 
                 exclude_groups = None, 
                 compound_idx = 0,
                 width = 12,
                 height = 6,
                 y_scale='linear',
                 alpha = 0.5,
                 min_max_color = 'sage',
                 peak_color = 'darkviolet',
                 slider_color = 'ghostwhite',
                 y_max = 'auto',
                 y_min = 0):
        """
        data: a metatlas_dataset where files and compounds are stored.
        for example, 
        self.metatlas_dataset[file_idx][compound_idx]['identification'].rt_references[-1].unique_id
        is the unique id to the retention time reference for a compound in a file.
        
        width: specify a width value in inches for the plots and slides
        height: specify a width value in inches for the plots and slides
        min_max_color & peak_color: specify a valid matplotlib color string for the slider and vertical bars
        slider_color: background color for the sliders. Must be a valid matplotlib color

        Press Left and Right arrow keys to move to the next or previous compound
        """
        
        self.compound_idx = compound_idx
        self.width = width
        self.height = height
        self.y_scale = y_scale
        self.alpha = alpha
        self.min_max_color = min_max_color
        self.peak_color = peak_color
        self.slider_color = slider_color
        self.y_max = y_max
        self.y_min = y_min
        
        # filter runs from the metatlas dataset
        if include_lcmsruns:
            data = filter_lcmsruns_in_dataset_by_include_list(data,'lcmsrun',include_lcmsruns)
        
        if include_groups:
            data = filter_lcmsruns_in_dataset_by_include_list(data,'group',include_groups)
        if exclude_lcmsruns:
            data = filter_lcmsruns_in_dataset_by_exclude_list(data,'lcmsrun',exclude_lcmsruns)
        if exclude_groups:
            data = filter_lcmsruns_in_dataset_by_exclude_list(data,'group',exclude_groups)     
        self.data = data
        
        # create figure and first axes
        self.fig,self.ax = plt.subplots(figsize=(width, height))
        plt.subplots_adjust(left=0.09, bottom=0.275)
#         plt.ticklabel_format(style='plain', axis='x')
#         plt.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
        
        # warn the user if they do not own the atlas; and can not edit its values
        self.enable_edit = True
        self.atlas = metob.retrieve('Atlas',unique_id = self.data[0][0]['atlas_unique_id'],username='*')[-1]
        print("loaded file for username = ", self.atlas.username)
        if getpass.getuser() != self.atlas.username:
            self.ax.set_title("YOUR ARE %s YOU ARE NOT ALLOWED TO EDIT VALUES THE RT CORRECTOR. USERNAMES ARE NOT THE SAME"%getpass.getuser())
            self.enable_edit = False
            
        #create all event handlers
        self.fig.canvas.callbacks.connect('pick_event', self.on_pick)
        self.fig.canvas.mpl_connect('key_press_event', self.press)

        #create the plot
        self.set_plot_data()
        

    def set_plot_data(self):
        self.ax.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
        self.ax.ticklabel_format(useOffset=False, style='plain', axis='x')
        
        default_data = self.data[0][self.compound_idx]
        if default_data['identification'].name:
            compound_str = default_data['identification'].name.split('///')[0]
        elif default_data['identification'].compound[-1].name:
            compound_str = default_data['identification'].compound[-1].name
        else:
            compound_str = 'nameless compound'
            
        compound_str = '%d, %s'%(self.compound_idx, compound_str)
        
        self.ax.set_title('')
        self.ax.set_ylabel('%s'%compound_str)
        self.ax.set_xlabel('Retention Time')
        self.my_mz = metob.retrieve('MZReference',
                               unique_id = default_data['identification'].mz_references[-1].unique_id, username='*')[-1]
        for i,d in enumerate(self.data): #this loops through the files
            if d[self.compound_idx]['data']['ms1_summary']:
#                 if len(d[self.compound_idx]['data']['ms1_summary']['rt']) > 0:
                    x = d[self.compound_idx]['data']['ms1_summary']['mz_centroid']
                    y = d[self.compound_idx]['data']['ms1_summary']['peak_height']
                    x = np.asarray(x)
                    y = np.asarray(y)
                    self.ax.plot(x,y,'k.',linewidth=2.0,alpha=self.alpha, picker=5, label = d[self.compound_idx]['lcmsrun'].name.replace('.mzML',''))
                    

        mz_delta = self.my_mz.mz_tolerance*self.my_mz.mz/1e6

        self.min_line = self.ax.axvline(self.my_mz.mz-mz_delta, color=self.min_max_color,linewidth=4.0)
        self.max_line = self.ax.axvline(self.my_mz.mz+mz_delta, color=self.min_max_color,linewidth=4.0)
        self.peak_line = self.ax.axvline(self.my_mz.mz, color=self.peak_color,linewidth=4.0)

        min_x = self.ax.get_xlim()[0]
        max_x = self.ax.get_xlim()[1]
        print(min_x,max_x)
        
        self.mz_peak_ax = plt.axes([0.09, 0.05, 0.81, 0.03], axisbg=self.slider_color)
        self.mz_max_ax = plt.axes([0.09, 0.1, 0.81, 0.03], axisbg=self.slider_color)
        self.mz_min_ax = plt.axes([0.09, 0.15, 0.81, 0.03], axisbg=self.slider_color)

        self.mz_min_slider = Slider(self.mz_min_ax, 'mz min', min_x, max_x, valinit=self.my_mz.mz-mz_delta,color=self.min_max_color,valfmt='%1.4f')
        self.mz_min_slider.vline.set_color('black')
        self.mz_min_slider.vline.set_linewidth(4)
        
        self.mz_max_slider = Slider(self.mz_max_ax, 'mz max', min_x, max_x, valinit=self.my_mz.mz+mz_delta,color=self.min_max_color,valfmt='%1.4f')
        self.mz_max_slider.vline.set_color('black')
        self.mz_max_slider.vline.set_linewidth(4)
        
        self.mz_peak_slider = Slider(self.mz_peak_ax,'mz peak', min_x, max_x, valinit=self.my_mz.mz,color=self.peak_color,valfmt='%1.4f')
        self.mz_peak_slider.vline.set_color('black')
        self.mz_peak_slider.vline.set_linewidth(4)
#         if self.enable_edit:
#             self.rt_min_slider.on_changed(self.update_rt)
#             self.rt_max_slider.on_changed(self.update_rt)
#             self.rt_peak_slider.on_changed(self.update_rt)

        self.lin_log_ax = plt.axes([0.1, 0.75, 0.1, 0.15])#, axisbg=axcolor)
        self.lin_log_ax.axis('off')
        self.lin_log_radio = RadioButtons(self.lin_log_ax, ('linear', 'log'))
        self.lin_log_radio.on_clicked(self.set_lin_log)
        
    def set_lin_log(self,label):
        self.ax.set_yscale(label)
        self.ax.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
        self.fig.canvas.draw_idle()
        
    def on_pick(self,event):
        thisline = event.artist
        thisline.set_color('red')
        self.ax.set_title(thisline.get_label())        
    
    def press(self,event):
        if event.key == 'right':
            if self.compound_idx + 1 < len(self.data[0]):
                self.compound_idx += 1
                self.ax.cla()
                self.mz_peak_ax.cla()
                self.mz_min_ax.cla()
                self.mz_max_ax.cla()
                self.set_plot_data()
        if event.key == 'left':
            if self.compound_idx > 0:
                self.compound_idx -= 1
                self.ax.cla()
                self.mz_peak_ax.cla()
                self.mz_min_ax.cla()
                self.mz_max_ax.cla()
                self.set_plot_data()
        
#     def update_rt(self,val):
#         self.my_rt.rt_min = self.rt_min_slider.val
#         self.my_rt.rt_max = self.rt_max_slider.val
#         self.my_rt.rt_peak = self.rt_peak_slider.val
        
#         self.rt_min_slider.valinit = self.my_rt.rt_min
#         self.rt_max_slider.valinit = self.my_rt.rt_max
#         self.rt_peak_slider.valinit = self.my_rt.rt_peak
        
#         metob.store(self.my_rt)
#         self.min_line.set_xdata((self.my_rt.rt_min,self.my_rt.rt_min))
#         self.max_line.set_xdata((self.my_rt.rt_max,self.my_rt.rt_max))
#         self.peak_line.set_xdata((self.my_rt.rt_peak,self.my_rt.rt_peak))
#         self.fig.canvas.draw_idle()


def replace_compound_id_with_name(x):
    id_list = literal_eval(x)
    if id_list:
        found_compound = metob.retrieve('Compounds',unique_id=id_list[0],username='*')
        return found_compound[-1].name
    else:
        return ''

def make_compound_id_df(data):
    ids = []
    for d in data[0]:
        ids.append(d['identification'])
    df = metob.to_dataframe(ids)
    df['compound'] = df['compound'].apply(replace_compound_id_with_name).astype('str') 
    df['rt_unique_id'] = df['rt_references'].apply(lambda x: literal_eval(x))
#     df['mz_unique_id'] = df['mz_references'].apply(lambda x: literal_eval(x))
#     df['frag_unique_id'] = df['frag_references'].apply(lambda x: literal_eval(x))
    df = df[['compound','name','username','rt_unique_id']]#,'mz_unique_id','frag_unique_id']]
    return df

def show_compound_grid(input_fname = '',input_dataset=[]):
    """
    Provide a valid path to data in or a dataset
    """
    if not input_dataset:
        print("loading...")
        data = ma_data.get_dill_data(input_fname)
    else:
        data = input_dataset
    atlas_in_data = metob.retrieve('Atlas',unique_id = data[0][0]['atlas_unique_id'],username='*')
    print("loaded file for username = ", atlas_in_data[0].username)
    username = getpass.getuser()
    if username != atlas_in_data[0].username:
        print("YOUR ARE", username, "YOU ARE NOT ALLOWED TO EDIT VALUES THE RT CORRECTOR. USERNAMES ARE NOT THE SAME")
        #return
    compound_df = make_compound_id_df(data)
    #compound_grid = gui.create_qgrid([])
    #compound_grid.df = compound_df
    compound_grid = qgrid.QGridWidget(df=compound_df)#,set_grid_option={'show_toolbar',True})
    #qgrid.show_grid(compound_df,show_toolbar=True)
    compound_grid.export()
    #display(compound_grid)
    return data,compound_grid



def getcommonletters(strlist):
    """
    Parameters
    ----------
    strlist

    Returns
    -------

    """
    return ''.join([x[0] for x in zip(*strlist) if reduce(lambda a,b:(a == b) and a or None,x)])


def findcommonstart(strlist):
    """
    Parameters
    ----------
    strlist

    Returns
    -------

    """
    strlist = strlist[:]
    prev = None
    while True:
        common = getcommonletters(strlist)
        if common == prev:
            break
        strlist.append(common)
        prev = common

    return getcommonletters(strlist)



def plot_all_compounds_for_each_file(input_dataset = [], input_fname = '', include_lcmsruns = [],exclude_lcmsruns = [], nCols = 8, scale_y=True , output_loc=''):

    """
    Parameters
    ----------
    kwargs

    Returns
    -------

    """

    if not input_dataset:
        data = ma_data.get_dill_data(os.path.expandvars(input_fname))
    else:
        data = input_dataset

    # filter runs from the metatlas dataset
    if include_lcmsruns:
        data = filter_lcmsruns_in_dataset_by_include_list(data,'lcmsrun',include_lcmsruns)
        data = filter_lcmsruns_in_dataset_by_include_list(data,'group',include_lcmsruns)

    if exclude_lcmsruns:
        data = filter_lcmsruns_in_dataset_by_exclude_list(data,'lcmsrun',exclude_lcmsruns)
        data = filter_lcmsruns_in_dataset_by_exclude_list(data,'group',exclude_lcmsruns)

    compound_names = ma_data.get_compound_names(data)[0]
    file_names = ma_data.get_file_names(data)


    output_loc = os.path.expandvars('output_loc')

    nRows = int(np.ceil(len(compound_names)/float(nCols)))

    
    xmin = 0
    xmax = 210
    subrange = float(xmax-xmin)/float(nCols) # scale factor for the x-axis
 
    y_max = list()
    if scale_y:
        for file_idx,my_file in enumerate(file_names):
            temp = -1
            counter = 0
            for compound_idx,compound in enumerate(compound_names):
                d = data[file_idx][compound_idx]
                if len(d['data']['eic']['rt']) > 0:
                    counter += 1
                    y = max(d['data']['eic']['intensity'])
                    if y > temp:
                        temp = y
            #y_max.append(temp)
            y_max += [temp] * counter
    else:
        for file_idx,my_file in enumerate(file_names):
            for compound_idx,compound in enumerate(compound_names):
                d = data[file_idx][compound_idx]
                if len(d['data']['eic']['rt']) > 0:
                    y_max.append(max(d['data']['eic']['intensity']))
    y_max = cycle(y_max)

    # create ouput dir
    if not os.path.exists(output_loc):
        os.makedirs(output_loc)


    for file_idx,my_file in enumerate(file_names):
        ax = plt.subplot(111)#, aspect='equal')
        plt.setp(ax, 'frame_on', False)
        ax.set_ylim([0, nRows+7])
      
        col = 0
        row = nRows+6
        counter = 1
        
        for compound_idx,compound in enumerate(compound_names):  
            if col == nCols:
                row -= 1.3
                col = 0
                        
            d = data[file_idx][compound_idx]

            rt_min = d['identification'].rt_references[0].rt_min
            rt_max = d['identification'].rt_references[0].rt_max
            rt_peak = d['identification'].rt_references[0].rt_peak

            if len(d['data']['eic']['rt']) > 0:
                x = d['data']['eic']['rt']
                y = d['data']['eic']['intensity']
                y = y/y_max.next()
                new_x = (x-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2) ## remapping the x-range
                xlbl = np.array_str(np.linspace(min(x), max(x), 8), precision=2)
                rt_min_ = (rt_min-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2)
                rt_max_ = (rt_max-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2)
                rt_peak_ = (rt_peak-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2)
                ax.plot(new_x, y+row,'k-')#,ms=1, mew=0, mfc='b', alpha=1.0)]
                #ax.annotate('plot={}'.format(col+1),(max(new_x)/2+col*subrange,row-0.1), size=5,ha='center')
                ax.annotate(xlbl,(min(new_x),row-0.1), size=2)
                ax.annotate('{0},{1},{2},{3}'.format(compound,rt_min, rt_peak, rt_max),(min(new_x),row-0.2), size=2)#,ha='center')
                myWhere = np.logical_and(new_x>=rt_min_, new_x<=rt_max_ )
                ax.fill_between(new_x,min(y)+row,y+row,myWhere, facecolor='c', alpha=0.3)
                col += 1
            else:
                new_x = np.asarray([0,1])#(x-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2) ## remapping the x-range
                ax.plot(new_x, new_x-new_x+row,'r-')#,ms=1, mew=0, mfc='b', alpha=1.0)]
                ax.annotate(compound,(min(new_x),row-0.1), size=2)
                col += 1
            counter += 1
        
        plt.title(my_file)
        fig = plt.gcf()
        fig.set_size_inches(nRows*1.0, nCols*4.0)
        fig.savefig(os.path.join(output_loc, my_file + '-' + str(counter) + '.pdf'))
        plt.clf()


def plot_all_files_for_each_compound(input_dataset = [], input_fname = '', include_lcmsruns = [],exclude_lcmsruns = [], nCols = 8, scale_y=True , output_loc=''):

    """
    Parameters
    ----------
    kwargs

    Returns
    -------

    """

    if not input_dataset:
        data = ma_data.get_dill_data(os.path.expandvars(input_fname))
    else:
        data = input_dataset

    # filter runs from the metatlas dataset
    if include_lcmsruns:
        data = filter_lcmsruns_in_dataset_by_include_list(data,'lcmsrun',include_lcmsruns)
        data = filter_lcmsruns_in_dataset_by_include_list(data,'group',include_lcmsruns)

    if exclude_lcmsruns:
        data = filter_lcmsruns_in_dataset_by_exclude_list(data,'lcmsrun',exclude_lcmsruns)
        data = filter_lcmsruns_in_dataset_by_exclude_list(data,'group',exclude_lcmsruns)

    compound_names = ma_data.get_compound_names(data)[0]
    file_names = ma_data.get_file_names(data)
    output_loc = os.path.expandvars(output_loc)

    nRows = int(np.ceil(len(file_names)/float(nCols)))
    print('nrows = ', nRows)
    
    xmin = 0
    xmax = 210
    subrange = float(xmax-xmin)/float(nCols) # scale factor for the x-axis
 

    y_max = list()
    if scale_y:
        for compound_idx,compound in enumerate(compound_names):
            temp = -1
            counter = 0
            for file_idx,my_file in enumerate(file_names):
                d = data[file_idx][compound_idx]
                if len(d['data']['eic']['rt']) > 0:
                    counter += 1
                    y = max(d['data']['eic']['intensity'])
                    if y > temp:
                        temp = y
            y_max += [temp] * counter
    else:
        for compound_idx,compound in enumerate(compound_names):
            for file_idx,my_file in enumerate(file_names):
                d = data[file_idx][compound_idx]
                if len(d['data']['eic']['rt']) > 0:
                    y_max.append(max(d['data']['eic']['intensity']))

    print("length of ymax is ", len(y_max))
    y_max = cycle(y_max)



    # create ouput dir
    if not os.path.exists(output_loc):
        os.makedirs(output_loc)
    plt.ioff()
    for compound_idx,compound in enumerate(compound_names):
        ax = plt.subplot(111)#, aspect='equal')
        plt.setp(ax, 'frame_on', False)
        ax.set_ylim([0, nRows+7])
      
        col = 0
        row = nRows+6
        counter = 1
        
        for file_idx,my_file in enumerate(file_names):  
            if col == nCols:
                row -= 1.3
                col = 0
                        
            d = data[file_idx][compound_idx]
            #file_name = compound_names[compound_idx]
                    
            rt_min = d['identification'].rt_references[0].rt_min
            rt_max = d['identification'].rt_references[0].rt_max
            rt_peak = d['identification'].rt_references[0].rt_peak

            if len(d['data']['eic']['rt']) > 0:
                x = d['data']['eic']['rt']
                y = d['data']['eic']['intensity']
                y = y/y_max.next()
                new_x = (x-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2) ## remapping the x-range
                xlbl = np.array_str(np.linspace(min(x), max(x), 8), precision=2)
                rt_min_ = (rt_min-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2)
                rt_max_ = (rt_max-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2)
                rt_peak_ = (rt_peak-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2)
                ax.plot(new_x, y+row,'k-')#,ms=1, mew=0, mfc='b', alpha=1.0)]
                #ax.annotate('plot={}'.format(col+1),(max(new_x)/2+col*subrange,row-0.1), size=5,ha='center')
                ax.annotate(xlbl,(min(new_x),row-0.1), size=2)
                ax.annotate('{0},{1},{2},{3}'.format(my_file,rt_min, rt_peak, rt_max),(min(new_x),row-0.2), size=2)#,ha='center')
                myWhere = np.logical_and(new_x>=rt_min_, new_x<=rt_max_ )
                #ax.fill_between(new_x,min(y)+row,y+row,myWhere, facecolor='c', alpha=0.3)
                col += 1
            else:
                new_x = np.asarray([0,1])
                ax.plot(new_x, new_x-new_x+row,'r-')#,ms=1, mew=0, mfc='b', alpha=1.0)]
#                 y = [0,1]#(x-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2) ## remapping the x-range
#                 ax.plot(new_x, y-y+row,'r-')#,ms=1, mew=0, mfc='b', alpha=1.0)]
                ax.annotate(my_file,(min(new_x),row-0.1), size=1)
                col += 1
            counter += 1
        
        plt.title(compound)
        fig = plt.gcf()
        fig.set_size_inches(nRows*1.0,nCols*4.0)

        fig.savefig(os.path.join(output_loc, compound + '-' + str(counter) + '.pdf'))
        plt.close(fig)


        
  


""" contribution from Hans de Winter """
def _InitialiseNeutralisationReactions():
    patts= (
        # Imidazoles
        ('[n+;H]','n'),
        # Amines
        ('[N+;!H0]','N'),
        # Carboxylic acids and alcohols
        ('[$([O-]);!$([O-][#7])]','O'),
        # Thiols
        ('[S-;X1]','S'),
        # Sulfonamides
        ('[$([N-;X2]S(=O)=O)]','N'),
        # Enamines
        ('[$([N-;X2][C,N]=C)]','N'),
        # Tetrazoles
        ('[n-]','[nH]'),
        # Sulfoxides
        ('[$([S-]=O)]','S'),
        # Amides
        ('[$([N-]C=O)]','N'),
        )
    return [(Chem.MolFromSmarts(x),Chem.MolFromSmiles(y,False)) for x,y in patts]


def desalt(mol):
    #input is an rdkit mol
    #returns an rdkit mol keeping the biggest component
    #returns original mol if only one component
    #returns a boolean indicated if cleaning was necessary
    d = Chem.rdmolops.GetMolFrags(mol) #these are atom indices
    if len(d) == 1: #If there are fragments or multiple molecules this will be greater than 1 
        return mol,False
    my_smiles=Chem.MolToSmiles(mol)
    parent_atom_count=0;
    disconnected=my_smiles.split('.')
    #With GetMolFrags, we've already established that there is more than one disconnected structure
    for s in disconnected:
        little_mol=Chem.MolFromSmiles(s)
        count = little_mol.GetNumAtoms()
        if count > parent_atom_count:
            parent_atom_count = count
            parent_mol = little_mol
    return parent_mol,True

""" contribution from Hans de Winter """
def _InitialiseNeutralisationReactions():
    patts= (
        # Imidazoles
        ('[n+;H]','n'),
        # Amines
        ('[N+;!H0]','N'),
        # Carboxylic acids and alcohols
        ('[$([O-]);!$([O-][#7])]','O'),
        # Thiols
        ('[S-;X1]','S'),
        # Sulfonamides
        ('[$([N-;X2]S(=O)=O)]','N'),
        # Enamines
        ('[$([N-;X2][C,N]=C)]','N'),
        # Tetrazoles
        ('[n-]','[nH]'),
        # Sulfoxides
        ('[$([S-]=O)]','S'),
        # Amides
        ('[$([N-]C=O)]','N'),
        )
    return [(Chem.MolFromSmarts(x),Chem.MolFromSmiles(y,False)) for x,y in patts]

def NeutraliseCharges(mol, reactions=None):
    reactions=_InitialiseNeutralisationReactions()
    replaced = False
    for i,(reactant, product) in enumerate(reactions):
        while mol.HasSubstructMatch(reactant):
            replaced = True
            rms = Chem.AllChem.ReplaceSubstructs(mol, reactant, product)
            rms_smiles = Chem.MolToSmiles(rms[0])
            mol = Chem.MolFromSmiles(rms_smiles)
    if replaced:
        return (mol, True) #Chem.MolToSmiles(mol,True)
    else:
        return (mol, False)
    

def drawStructure_Fragment(pactolus_tree,fragment_idx,myMol,myMol_w_Hs):
    from copy import deepcopy
    fragment_atoms = np.where(pactolus_tree[fragment_idx]['atom_bool_arr'])[0]
    depth_of_hit = np.sum(pactolus_tree[fragment_idx]['bond_bool_arr'])
    mol2 = deepcopy(myMol_w_Hs)
    # Now set the atoms you'd like to remove to dummy atoms with atomic number 0
    fragment_atoms = np.where(pactolus_tree[fragment_idx]['atom_bool_arr']==False)[0]
    for f in fragment_atoms:
        mol2.GetAtomWithIdx(f).SetAtomicNum(0)

    # Now remove dummy atoms using a query
    mol3 = Chem.DeleteSubstructs(mol2, Chem.MolFromSmarts('[#0]'))
    mol3 = Chem.RemoveHs(mol3)
    # You get what you are looking for
    return moltosvg(mol3),depth_of_hit


def moltosvg(mol,molSize=(450,150),kekulize=True):
    mc = Chem.Mol(mol.ToBinary())
    if kekulize:
        try:
            Chem.Kekulize(mc)
        except:
            mc = Chem.Mol(mol.ToBinary())
    if not mc.GetNumConformers():
        rdDepictor.Compute2DCoords(mc)
    drawer = rdMolDraw2D.MolDraw2DSVG(molSize[0],molSize[1])
    drawer.DrawMolecule(mc)
    drawer.FinishDrawing()
    svg = drawer.GetDrawingText()
    # It seems that the svg renderer used doesn't quite hit the spec.
    # Here are some fixes to make it work in the notebook, although I think
    # the underlying issue needs to be resolved at the generation step
    return svg.replace('svg:','')

def get_ion_from_fragment(frag_info,spectrum):
    hit_indices = np.where(np.sum(frag_info,axis=1))
    hit = spectrum[hit_indices,:][0]
    return hit,hit_indices



#plot msms and annotate
#compound name
#formula
#adduct
#theoretical m/z
#histogram of retention times
#scatter plot of retention time with peak area
#retention time
#print all chromatograms
#structure

def make_output_dataframe(input_fname = '',input_dataset = [],include_lcmsruns = [],exclude_lcmsruns = [], include_groups = [],exclude_groups = [], output_loc = [], fieldname = 'peak_height'):
    """
    fieldname can be: peak_height, peak_area, mz_centroid, rt_centroid, mz_peak, rt_peak
    """
    if not input_dataset:
        data = ma_data.get_dill_data(os.path.expandvars(input_fname))
    else:
        data = input_dataset

    # filter runs from the metatlas dataset
    if include_lcmsruns:
        data = filter_lcmsruns_in_dataset_by_include_list(data,'lcmsrun',include_lcmsruns)
    if include_groups:
        data = filter_lcmsruns_in_dataset_by_include_list(data,'group',include_groups)

    if exclude_lcmsruns:
        data = filter_lcmsruns_in_dataset_by_exclude_list(data,'lcmsrun',exclude_lcmsruns)
    if exclude_groups:
        data = filter_lcmsruns_in_dataset_by_exclude_list(data,'group',exclude_groups)

    compound_names = ma_data.get_compound_names(data)[0]
    file_names = ma_data.get_file_names(data)
    group_names = ma_data.get_group_names(data)
    output_loc = os.path.expandvars(output_loc)
    fieldname = fieldname
    
    df = pd.DataFrame( index=compound_names, columns=file_names, dtype=float)

    # peak_height['compound'] = compound_list
    # peak_height.set_index('compound',drop=True)
    for i,dd in enumerate(data):
        for j,d in enumerate(dd):
            if (not d['data']['ms1_summary']) or (not d['data']['ms1_summary'][fieldname]):
                df.ix[compound_names[j],file_names[i]] = 0
            else:
                df.ix[compound_names[j],file_names[i]] = d['data']['ms1_summary'][fieldname]  
    columns = []
    for i,f in enumerate(file_names):
        columns.append((group_names[i],f))
    df.columns = pd.MultiIndex.from_tuples(columns,names=['group', 'file'])

    if output_loc:    
        if not os.path.exists(output_loc):
            os.makedirs(output_loc)
        df.to_csv(os.path.join(output_loc, fieldname + '.tab'),sep='\t')

    return df

def file_with_max_precursor_intensity(data,compound_idx):
    idx = []
    my_max = 0
    for i,d in enumerate(data):
        if 'data' in d[compound_idx]['data']['msms'].keys():
            if type(d[compound_idx]['data']['msms']['data']) != list:#.has_key('precursor_intensity'):
                temp = d[compound_idx]['data']['msms']['data']['precursor_intensity']
                if len(temp)>0:
                    m = max(temp)
                    if m > my_max:
                        my_max = m
                        idx = i
    return idx,my_max

def file_with_max_score(data, frag_refs, compound_idx, filter_by):
    idx = []
    max_score = 0
    best_ref_spec = []
    
    for file_idx in range(len(data)):
        if 'data' in data[file_idx][compound_idx]['data']['msms'].keys():
            data_mz = np.array([data[file_idx][compound_idx]['data']['msms']['data']['mz'], data[file_idx][compound_idx]['data']['msms']['data']['i']])
            
            for f, frag in sp.filter_frag_refs(data, frag_refs, compound_idx, file_idx, filter_by).iterrows():
                ref_mz = np.array(frag['mz_intensities']).T

                score = sp.score_vectors_composite_dot(*sp.align_vectors(*sp.partition_ms_vectors(data_mz, ref_mz, .005, "intensity")))

                if score > max_score:
                    max_score = score
                    idx = file_idx
                    best_ref_spec = [frag['mz_intensities']]
                
    return idx, max_score, best_ref_spec

def plot_errorbar_plots(df,output_loc=''):
    
    output_loc = os.path.expandvars(output_loc)
    if not os.path.exists(output_loc):
        os.makedirs(output_loc)
        
    plt.ioff()
    for compound in df.index:
        m = df.ix[compound].groupby(level='group').mean()
        e = df.ix[compound].groupby(level='group').std()
        c = df.ix[compound].groupby(level='group').count()

        for i in range(len(e)):
            if c[i]>0:
                e[i] = e[i] / c[i]**0.5
        
        f, ax = plt.subplots(1, 1,figsize=(12,12))
        m.plot(yerr=e, kind='bar',ax=ax)
        ax.set_title(compound,fontsize=12,weight='bold')
        plt.tight_layout()
        f.savefig(os.path.join(output_loc, compound + '_errorbar.pdf'))

        #f.clear()
        plt.close(f)#f.clear()

def frag_refs_to_json(json_dir = '/project/projectdirs/metatlas/projects/sharepoint/', name = 'frag_refs', save = True):
    ids = metob.retrieve('CompoundIdentification',username='*')
    frag_refs = [cid for cid in ids if cid.frag_references]

    data = {'head_id': [], 
            'inchi_key': [],
            'neutralized_inchi_key': [],
            'neutralized_2d_inchi_key': [],
            'polarity': [],
            'collision_energy': [],
            'technique': [],
            'precursor_mz': [],
            'mz_intensities': []}

    for fr in frag_refs:
        data['head_id'].append(fr.frag_references[0].head_id), 
        data['inchi_key'].append(fr.compound[0].inchi_key)
        data['neutralized_inchi_key'].append(fr.compound[0].neutralized_inchi_key)
        data['neutralized_2d_inchi_key'].append(fr.compound[0].neutralized_2d_inchi_key)
        data['polarity'].append(fr.frag_references[0].polarity)
        data['precursor_mz'].append(fr.frag_references[0].precursor_mz)
        data['mz_intensities'].append([(m.mz, m.intensity) for m in fr.frag_references[0].mz_intensities])
        data['collision_energy'].append(fr.frag_references[0].collision_energy)
        data['technique'].append(fr.frag_references[0].technique)

    if save:
        with open(os.path.join(json_dir, name + '.json'), 'w') as text_file:
            text_file.write(json.dumps(data))
    else:
        return json.dumps(data)

# def get_idenficications_with_fragrefs():
#     """
#     Select all CompoundIdentifications that have a fragmentation reference
#     """
    

def make_identification_figure(frag_json_dir = '/project/projectdirs/metatlas/projects/sharepoint/', frag_json_name = 'frag_refs', 
    input_fname = '', input_dataset = [], include_lcmsruns = [], 
    exclude_lcmsruns = [], include_groups = [], exclude_groups = [], output_loc = [], use_labels=False):
    output_loc = os.path.expandvars(output_loc)    
    if not os.path.exists(output_loc):
        os.makedirs(output_loc)
    
    if not input_dataset:
        data = ma_data.get_dill_data(os.path.expandvars(input_fname))
    else:
        data = input_dataset
    
    # filter runs from the metatlas dataset
    if include_lcmsruns:
        data = filter_lcmsruns_in_dataset_by_include_list(data,'lcmsrun',include_lcmsruns)
    if include_groups:
        data = filter_lcmsruns_in_dataset_by_include_list(data,'group',include_groups)
        
    if exclude_lcmsruns:
        data = filter_lcmsruns_in_dataset_by_exclude_list(data,'lcmsrun',exclude_lcmsruns)
    if exclude_groups:
        data = filter_lcmsruns_in_dataset_by_exclude_list(data,'lcmsrun',exclude_groups)
        #data = filter_lcmsruns_in_dataset_by_exclude_list(data,'group',exclude_lcmsruns)
    
    
    compound_names = ma_data.get_compound_names(data,use_labels=use_labels)[0]
    file_names = ma_data.get_file_names(data)
    # print(len(data),len(data[0]),len(compound_names))
    

    frag_refs = pd.read_json(os.path.join(frag_json_dir, frag_json_name + ".json"))
    
    
    for compound_idx in range(len(compound_names)):
        file_idx = None
        file_precursor_intensity = 0
        score = None
        ref_spec = []

        if any([(len(data[i][compound_idx]['identification'].compound)!=0) and (data[i][compound_idx]['identification'].compound is not None) for i in range(len(file_names))]):
            # print('checking for compound ids')
            file_idx, score, ref_spec = file_with_max_score(data, frag_refs, compound_idx, 'inchi_key and rt and polarity')
            if ~isinstance(file_idx,int): #There is not a reference for that compound
                file_idx = file_with_max_precursor_intensity(data,compound_idx)[0]        
            # print('found one',file_idx)
        else:
            file_idx = file_with_max_precursor_intensity(data,compound_idx)[0]        
        # print(file_idx,compound_idx, compound_names[compound_idx])
        if isinstance(file_idx,int):
            # print('printing')
            # print(file_idx,compound_idx)
            fig = plt.figure(figsize=(20,20))
        #     fig = plt.figure()
            ax = fig.add_subplot(211)
            ax.set_title(compound_names[compound_idx],fontsize=12,weight='bold')
            ax.set_xlabel('m/z',fontsize=12,weight='bold')
            ax.set_ylabel('intensity',fontsize=12,weight='bold')

            #TODO: iterate across all collision energies
            precursor_intensity = data[file_idx][compound_idx]['data']['msms']['data']['precursor_intensity']
            idx_max = np.argwhere(precursor_intensity == np.max(precursor_intensity)).flatten() 

            mz = data[file_idx][compound_idx]['data']['msms']['data']['mz'][idx_max]
            zeros = np.zeros(data[file_idx][compound_idx]['data']['msms']['data']['mz'][idx_max].shape)
            intensity = data[file_idx][compound_idx]['data']['msms']['data']['i'][idx_max]

            ax.vlines(mz,zeros,intensity,colors='r',linewidth = 2)
            sx = np.argsort(intensity)[::-1]
            labels = [1.001e9]
            for i in sx:
                if np.min(np.abs(mz[i] - labels)) > 0.1 and intensity[i] > 0.02 * np.max(intensity):
                    ax.annotate('%5.4f'%mz[i], xy=(mz[i], 1.01*intensity[i]),rotation = 90, horizontalalignment = 'center', verticalalignment = 'left')
                    labels.append(mz[i])

            
#                                        precursor_mz = data[file_idx][compound_idx]['data']['msms']['precursor_mz'])
#             print data[file_idx][compound_idx]['data']['msms']['polarity']
            if ref_spec:
                ref_mz = []
                ref_intensity = []
                ref_zeros = []
                for s in ref_spec[0]:
                    ref_mz.append(s[0])
                    ref_intensity.append(s[1]*-1)
                    ref_zeros.append(0)
                s = -1* intensity[sx[0]] / min(ref_intensity)

#                 L = plt.ylim()
#                 print data[file_idx][compound_idx]['identification'].compound[0].name, float(intensity[sx[0]]), float(min(ref_intensity))
                ax.vlines(ref_mz,ref_zeros,[r*s for r in ref_intensity],colors='r',linewidth = 2)
#                 print "we have reference spectra", len(ref_spec[0])
            plt.ioff()
            plt.axhline()
            plt.tight_layout()
            L = plt.ylim()
            plt.ylim(L[0],L[1]*1.12)
            if data[file_idx][compound_idx]['identification'].compound:
                inchi =  data[file_idx][compound_idx]['identification'].compound[0].inchi
                myMol = Chem.MolFromInchi(inchi.encode('utf-8'))
                # myMol,neutralised = NeutraliseCharges(myMol)
                if myMol:
                    image = Draw.MolToImage(myMol, size = (300,300) )
                    ax2 = fig.add_subplot(223)
                    ax2.imshow(image)
                    ax2.axis('off')
            #     SVG(moltosvg(myMol))

            ax3 = fig.add_subplot(224)
            ax3.set_xlim(0,1)
            mz_theoretical = data[file_idx][compound_idx]['identification'].mz_references[0].mz
            mz_measured = data[file_idx][compound_idx]['data']['ms1_summary']['mz_centroid']
            if not mz_measured:
                mz_measured = 0

            delta_mz = abs(mz_theoretical - mz_measured)
            delta_ppm = delta_mz / mz_theoretical * 1e6

            rt_theoretical = data[file_idx][compound_idx]['identification'].rt_references[0].rt_peak
            rt_measured = data[file_idx][compound_idx]['data']['ms1_summary']['rt_peak']
            if not rt_measured:
                rt_measured = 0
            ax3.text(0,1,'%s'%os.path.basename(data[file_idx][compound_idx]['lcmsrun'].hdf5_file),fontsize=12)
            ax3.text(0,0.95,'%s %s'%(compound_names[compound_idx], data[file_idx][compound_idx]['identification'].mz_references[0].adduct),fontsize=12)
            ax3.text(0,0.9,'m/z theoretical = %5.4f, measured = %5.4f, %5.4f ppm difference'%(mz_theoretical, mz_measured, delta_ppm),fontsize=12)
            ax3.text(0,0.85,'Expected Elution of %5.2f minutes, %5.2f min actual'%(rt_theoretical,rt_measured),fontsize=12)
            if score != None:
                ax3.text(0,0.80,'Score: %f'%(score),fontsize=12)
            ax3.set_ylim(0.2,1.01)
            ax3.axis('off')
        #     plt.show()
            fig.savefig(os.path.join(output_loc, compound_names[compound_idx] + '.pdf'))
            plt.close()


def top_five_scoring_files(data, frag_refs, compound_idx, filter_by):
    file_idxs = []
    ref_idxs = []
    scores = []
    sample_matches_list = []
    ref_matches_list = []
    sample_nonmatches_list = []
    ref_nonmatches_list = []
    
    for file_idx in range(len(data)):
        if 'data' in data[file_idx][compound_idx]['data']['msms'].keys():
            current_best_score = None
            current_best_ref_idx = None
            current_best_sample_matches = None
            current_best_ref_matches = None
            current_best_sample_nonmatches = None
            current_best_ref_nonmatches = None
            
            sample_mzi = np.array([data[file_idx][compound_idx]['data']['msms']['data']['mz'], data[file_idx][compound_idx]['data']['msms']['data']['i']])
            
            for ref_idx, frag in sp.filter_frag_refs(data, frag_refs, compound_idx, file_idx, filter_by).iterrows():
                ref_mzi = np.array(frag['mz_intensities']).T
                
                sample_matches, ref_matches, sample_nonmatches, ref_nonmatches = sp.partition_ms_vectors(sample_mzi, ref_mzi, .005, 'intensity')
                
                sample_aligned, ref_aligned = sp.align_vectors(sample_matches, ref_matches, sample_nonmatches, ref_nonmatches) 
                
                score = sp.score_vectors_composite_dot(sample_aligned, ref_aligned)
                
                if current_best_score == None or score > current_best_score:
                    current_best_score = score
                    current_best_ref_idx = ref_idx
                    current_best_sample_matches = sample_matches
                    current_best_ref_matches = ref_matches
                    current_best_sample_nonmatches = sample_nonmatches
                    current_best_ref_nonmatches = ref_nonmatches
            
            if current_best_score:
                scores.append(current_best_score)
                file_idxs.append(file_idx)
                ref_idxs.append(current_best_ref_idx)
                sample_matches_list.append(current_best_sample_matches)
                ref_matches_list.append(current_best_ref_matches)
                sample_nonmatches_list.append(current_best_sample_nonmatches)
                ref_nonmatches_list.append(current_best_ref_nonmatches)
    
    return zip(*sorted(zip(file_idxs, ref_idxs, scores, sample_matches_list, ref_matches_list, sample_nonmatches_list, ref_nonmatches_list), key=lambda l: l[2], reverse=True)[:5])
            
            
def plot_msms_comparison(i, score, ax, precursor_intensity, sample_matches, ref_matches, sample_nonmatches, ref_nonmatches):
    
    full_sample = np.concatenate((sample_matches, sample_nonmatches), axis=1)
    full_ref = np.concatenate((ref_matches, ref_nonmatches), axis=1)
    
    sample_mz = sample_nonmatches[0]
    sample_zeros = np.zeros(sample_nonmatches[0].shape)
    sample_intensity = sample_nonmatches[1]

    ax.vlines(sample_mz, sample_zeros, sample_intensity, colors='r', linewidth = 1)

    shared_mz = sample_matches[0,]
    shared_zeros = np.zeros(sample_matches[0].shape)
    shared_sample_intensity = sample_matches[1]

    ax.vlines(shared_mz, shared_zeros, shared_sample_intensity, colors='g', linewidth = 1)

    most_intense_idxs = np.argsort(full_sample[1])[::-1]

    if i == 0:
        ax.set_title('%.4f'%score,fontsize=8,weight='bold')
        ax.set_xlabel('m/z',fontsize=8,weight='bold')
        ax.set_ylabel('intensity',fontsize=8,weight='bold')
        ax.tick_params(axis='both', which='major', labelsize=6)

        labels = [1.001e9]
        
        intensity_requirement = [m for m in most_intense_idxs 
                                 if np.min(np.abs(full_sample[0][m] - labels)) > 0.1 and full_sample[1][m] > 0.2 * np.max(full_sample[1])]
        
        for m in max([most_intense_idxs[:6], intensity_requirement], key=len):
            if np.min(np.abs(full_sample[0][m] - labels)) > 0.1 and full_sample[1][m] > 0.02 * np.max(full_sample[1]):
                ax.annotate('%5.4f'%full_sample[0][m], 
                            xy=(full_sample[0][m], 1.01*full_sample[1][m]),
                            rotation = 90, 
                            horizontalalignment = 'center', verticalalignment = 'left',
                            fontsize = 5)
                labels.append(full_sample[0][m])
 
    if full_ref[0].size > 0:
        ref_scale = -1*np.max(full_sample[1]) / np.max(full_ref[1])
        
        ref_mz = ref_nonmatches[0]
        ref_zeros = np.zeros(ref_nonmatches[0].shape)
        ref_intensity = ref_scale*ref_nonmatches[1]
        shared_ref_intensity = ref_scale*ref_matches[1]
    
        ax.vlines(ref_mz, ref_zeros, ref_intensity, colors='r', linewidth = 1)

        ax.vlines(shared_mz, shared_zeros, shared_ref_intensity, colors='g', linewidth = 1)

        ax.axhline()
        
    ylim = ax.get_ylim()
    ax.set_ylim(ylim[0], ylim[1]*1.33)
            
            
def plot_structure(ax, compound, dimensions):
    if compound:
        inchi =  compound[0].inchi
        myMol = Chem.MolFromInchi(inchi.encode('utf-8'))
        
        if myMol:
            image = Draw.MolToImage(myMol, size=(dimensions, dimensions))
            ax.imshow(image)
            
    ax.axis('off')            
            
            
def plot_ema_compound_info(ax, compound_info):
    wrapper = TextWrapper(width=28, break_on_hyphens=True)
    
    if compound_info.compound:
        name = ['Name:', wrapper.fill(compound_info.compound[0].name)]
        label = ['Label:', '']
        formula = ['Formula:', compound_info.compound[0].formula]
        polarity = ['Polarity:', compound_info.mz_references[0].detected_polarity]
        neutral_mass = ['Monoisotopic Mass:', compound_info.compound[0].mono_isotopic_molecular_weight]
        theoretical_mz = ['Theoretical M/Z:', compound_info.mz_references[0].mz]
        adduct = ['Adduct:', compound_info.mz_references[0].adduct]
        
        cell_text = [name, label, formula, polarity, neutral_mass, theoretical_mz, adduct]
        
        ema_compound_info_table = ax.table(cellText=cell_text,
                                           colLabels=['', 'EMA Compound Info'],
                                           bbox=[0.0, 0.0, 1, 1], loc='top left')
        ema_compound_info_table.scale(1, .7)
        ema_compound_info_table.auto_set_font_size(False)
        ema_compound_info_table.set_fontsize(5)
        
        cellDict = ema_compound_info_table.get_celld()
        for i in range(len(cell_text)+1):
            cellDict[(i,0)].set_width(0.3)
            cellDict[(i,1)]._loc = 'center'
            
    ax.axis('off')
            
    
def plot_eic(ax, data, file_idxs, compound_idx):
    for file_idx in file_idxs:
    
        rt_min = data[file_idx][compound_idx]['identification'].rt_references[0].rt_min
        rt_max = data[file_idx][compound_idx]['identification'].rt_references[0].rt_max
        rt_peak = data[file_idx][compound_idx]['identification'].rt_references[0].rt_peak

        if len(data[file_idx][compound_idx]['data']['eic']['rt']) > 1:
            x = np.asarray(data[file_idx][compound_idx]['data']['eic']['rt'])
            y = np.asarray(data[file_idx][compound_idx]['data']['eic']['intensity'])

            ax.plot(x, y, 'k-', linewidth=.5, alpha=1.0)  
            myWhere = np.logical_and(x>=rt_min, x<=rt_max )
            ax.fill_between(x,0,y,myWhere, facecolor='c', alpha=0.2)

    ax.tick_params(labelbottom='off')
    ax.tick_params(labelleft='off')
    ax.axvline(rt_min, color='k', linewidth=1.0)
    ax.axvline(rt_max, color='k', linewidth=1.0)
    ax.axvline(rt_peak, color='r', linewidth=1.0)   
    
    
def plot_score_and_ref_file(ax, score, ref):
    ax.text(0.5, 1, '%.4f'%score,
        weight='bold',
        horizontalalignment='center',
        verticalalignment='top',
        fontsize=5,
        transform=ax.transAxes)
    
    ax.text(0, .45, fill(ref, width=28),
        horizontalalignment='left',
        verticalalignment='center',
        rotation='vertical',
        fontsize=2,
        transform=ax.transAxes)
            
            
def make_identification_figure_v2(frag_refs_json = '/project/projectdirs/metatlas/projects/sharepoint/frag_refs.json', 
    input_fname = '', input_dataset = [], include_lcmsruns = [], exclude_lcmsruns = [], include_groups = [], 
    exclude_groups = [], output_loc = [],use_labels=False):
    
    if not os.path.exists(output_loc):
        os.makedirs(output_loc)
    
    if not input_dataset:
        data = ma_data.get_dill_data(os.path.expandvars(input_fname))
    else:
        data = input_dataset

    #Filter runs from the metatlas dataset
    if include_lcmsruns:
        data = filter_lcmsruns_in_dataset_by_include_list(data, 'lcmsrun', include_lcmsruns)
    if include_groups:
        data = filter_lcmsruns_in_dataset_by_include_list(data, 'group', include_groups)
        
    if exclude_lcmsruns:
        data = filter_lcmsruns_in_dataset_by_exclude_list(data, 'lcmsrun', exclude_lcmsruns)
    if exclude_groups:
        data = filter_lcmsruns_in_dataset_by_exclude_list(data, 'group', exclude_groups)

    #Obtain compound and file names
    compound_names = ma_data.get_compound_names(data,use_labels)[0]
    file_names = ma_data.get_file_names(data)
    
    #Obtain fragmentation references
    frag_refs = pd.read_json(frag_refs_json)
    
    #Turn off interactive plotting
    plt.ioff()
    
    #Iterate over compounds
    for compound_idx in range(len(compound_names)):
        file_idxs, ref_idxs, scores = [], [], []
        sample_matches_list, ref_matches_list, sample_nonmatches_list, ref_nonmatches_list = [], [], [], []
        
        #Find 5 best file and reference pairs by score
        if any([data[i][compound_idx]['identification'].compound for i in range(len(file_names))]):
            top_five = top_five_scoring_files(data, frag_refs, compound_idx, 'inchi_key and rt and polarity')
            if top_five:
                file_idxs, ref_idxs, scores, sample_matches_list, ref_matches_list, sample_nonmatches_list, ref_nonmatches_list = top_five
            else:
                file_idx = file_with_max_precursor_intensity(data,compound_idx)[0]
                if file_idx:
                    file_idxs.append(file_idx)
                    sample_nonmatches_list.append(np.array([np.array(data[file_idx][compound_idx]['data']['msms']['data']['mz']), np.array(data[file_idx][compound_idx]['data']['msms']['data']['i'])]))
                    sample_matches_list.append(np.array([[],[]]))
                    ref_matches_list.append(np.array([[],[]]))
                    ref_nonmatches_list.append(np.array([[],[]]))
                    scores.append(0)
        
        #Find best file by prescursor intensity
        else:
            file_idx = file_with_max_precursor_intensity(data,compound_idx)[0]
            if file_idx:
                file_idxs.append(file_idx)
                sample_nonmatches_list.append(np.array([np.array(data[file_idx][compound_idx]['data']['msms']['data']['mz']), np.array(data[file_idx][compound_idx]['data']['msms']['data']['i'])]))
                sample_matches_list.append(np.array([[],[]]))
                ref_matches_list.append(np.array([[],[]]))
                ref_nonmatches_list.append(np.array([[],[]]))
                scores.append(0)
                
        #Plot if compound yields any scores 
        if file_idxs:

            #Top 5 MSMS Spectra
            ax1 = plt.subplot2grid((24, 24), (0, 0), rowspan=12, colspan=12)
            ax2a = plt.subplot2grid((24, 24), (0, 12), rowspan=3, colspan=3)
            ax2a.tick_params(axis='both', length=2)
            ax2a.set_xticklabels([])
            ax2a.set_yticklabels([])
            ax2b = plt.subplot2grid((24, 24), (3, 12), rowspan=3, colspan=3)
            ax2b.tick_params(axis='both', length=2)
            ax2b.set_xticklabels([])
            ax2b.set_yticklabels([])
            ax2c = plt.subplot2grid((24, 24), (6, 12), rowspan=3, colspan=3)
            ax2c.tick_params(axis='both', length=2)
            ax2c.set_xticklabels([])
            ax2c.set_yticklabels([])
            ax2d = plt.subplot2grid((24, 24), (9, 12), rowspan=3, colspan=3)
            ax2d.tick_params(axis='both', length=2)
            ax2d.set_xticklabels([])
            ax2d.set_yticklabels([])
            
            for i,(score,ax) in enumerate(zip(scores,[ax1, ax2a, ax2b, ax2c, ax2d])):
                plot_msms_comparison(i, score, ax,
                                     data[file_idxs[i]][compound_idx]['data']['msms']['data']['precursor_intensity'],
                                     sample_matches_list[i], ref_matches_list[i], sample_nonmatches_list[i], ref_nonmatches_list[i])                    
            
            #EMA Compound Info
            ax3 = plt.subplot2grid((24, 24), (0, 16), rowspan=6, colspan=8)
            plot_ema_compound_info(ax3, data[file_idxs[0]][compound_idx]['identification'])
            
            #Next Best Scores and Filenames
            ax4a = plt.subplot2grid((24, 24), (0, 15), rowspan=3, colspan=1)
            ax4a.axis('off')
            ax4b = plt.subplot2grid((24, 24), (3, 15), rowspan=3, colspan=1)
            ax4b.axis('off')
            ax4c = plt.subplot2grid((24, 24), (6, 15), rowspan=3, colspan=1)
            ax4c.axis('off')
            ax4d = plt.subplot2grid((24, 24), (9, 15), rowspan=3, colspan=1)
            ax4d.axis('off')
            
            for i,(score,ax) in enumerate(zip(scores[1:],[ax4a, ax4b, ax4c, ax4d])):
                plot_score_and_ref_file(ax, score, os.path.basename(data[file_idxs[i]][compound_idx]['lcmsrun'].hdf5_file))
                
            #Structure
            ax5 = plt.subplot2grid((24, 24), (13, 0), rowspan=6, colspan=6)
            plot_structure(ax5, data[file_idxs[0]][compound_idx]['identification'].compound, 100)
            
            #EIC
            ax6 = plt.subplot2grid((24, 24), (6, 16), rowspan=6, colspan=6)
            plot_eic(ax6, data, file_idxs, compound_idx)
            
#             #Reference and Sample Info
#             ax10 = plt.subplot2grid((24, 24), (14, 6), rowspan=10, colspan=20)
#             plot_ref_sample_info(ax10, 1, 1)
            
            #Old code
            ax7 = plt.subplot2grid((24, 24), (15, 6), rowspan=9, colspan=20)
            mz_theoretical = data[file_idxs[0]][compound_idx]['identification'].mz_references[0].mz
            mz_measured = data[file_idxs[0]][compound_idx]['data']['ms1_summary']['mz_centroid']
            if not mz_measured:
                mz_measured = 0

            delta_mz = abs(mz_theoretical - mz_measured)
            delta_ppm = delta_mz / mz_theoretical * 1e6

            rt_theoretical = data[file_idxs[0]][compound_idx]['identification'].rt_references[0].rt_peak
            rt_measured = data[file_idxs[0]][compound_idx]['data']['ms1_summary']['rt_peak']
            if not rt_measured:
                rt_measured = 0    
            ax7.text(0,1,'%s'%fill(os.path.basename(data[file_idxs[0]][compound_idx]['lcmsrun'].hdf5_file), width=54),fontsize=8)
            ax7.text(0,0.9,'%s %s'%(compound_names[compound_idx], data[file_idxs[0]][compound_idx]['identification'].mz_references[0].adduct),fontsize=8)
            ax7.text(0,0.85,'Measured M/Z = %5.4f, %5.4f ppm difference'%(mz_measured, delta_ppm),fontsize=8)
            ax7.text(0,0.8,'Expected Elution of %5.2f minutes, %5.2f min actual'%(rt_theoretical,rt_measured),fontsize=8)
            ax7.set_ylim(0.2,1.01)
            ax7.axis('off')

            plt.savefig(os.path.join(output_loc, compound_names[compound_idx] + '.pdf'))
            plt.close()
            
            
def plot_ms1_spectra(polarity = None, mz_min = 5, mz_max = 5, input_fname = '', input_dataset = [], compound_names = [],  include_lcmsruns = [], exclude_lcmsruns = [], include_groups = [], exclude_groups = [], output_loc = []):
    """
    Plot three views of ms1 spectra for compounds in input_dataset using file with highest RT peak of a polarity:
    Unscaled: plots ms1 spectra within window of mz_min and mz_max
    Scaled: plots ms1 spectra within window of mz_min and mz_max scaling mz of compound to 70%
    Full Range: plots ms1 spectra without window (unscaled)
    """
    
    if not input_dataset:
        data = ma_data.get_dill_data(os.path.expandvars(input_fname))
    else:
        data = input_dataset
        
    if include_lcmsruns:
        data = filter_lcmsruns_in_dataset_by_include_list(data, 'lcmsrun', include_lcmsruns)
    if include_groups:
        data = filter_lcmsruns_in_dataset_by_include_list(data, 'group', include_groups)

    if exclude_lcmsruns:
        data = filter_lcmsruns_in_dataset_by_exclude_list(data, 'lcmsrun', exclude_lcmsruns)
    if exclude_groups:
        data = filter_lcmsruns_in_dataset_by_exclude_list(data, 'group', exclude_groups)
    
    #Make sure there is data
    assert(len(data) != 0)
    
    all_compound_names = ma_data.get_compound_names(data)[0]
    
    #Set default compound list to all compounds in input_dataset
    if not compound_names:
        compound_names = all_compound_names
    
    #Find implicit polarity and make sure there is not more than one
    if 'POS' in include_lcmsruns or 'NEG' in exclude_lcmsruns:
        assert(polarity == None or polarity == 'positive')
        polarity = 'positive'
    if 'NEG' in include_lcmsruns or 'POS' in exclude_lcmsruns:
        assert(polarity == None or polarity == 'negative')
        polarity = 'negative'
        
    if 'POS' in include_groups or 'NEG' in exclude_groups:
        assert(polarity == None or polarity == 'positive')
        polarity = 'positive'
    if 'NEG' in include_groups or 'POS' in exclude_groups:
        assert(polarity == None or polarity == 'negative')
        polarity = 'negative'
    
    assert(polarity == 'positive' or polarity == 'negative')
    
    #Additional variables used acorss all compounds
    lcms_polarity = 'ms1_' + polarity[:3]
    titles = ['Unscaled', 'Scaled', 'Full Range']
    
    for compound_idx in [i for i,c in enumerate(all_compound_names) if c in compound_names]:

        #Find file_idx of with highest RT peak
        highest = 0
        file_idx = None
        for i,d in enumerate(data):
            if d[compound_idx]['identification'].mz_references[0].detected_polarity == polarity:
                if d[compound_idx]['data']['ms1_summary']['peak_height'] > highest:
                    highest = d[compound_idx]['data']['ms1_summary']['peak_height']
                    file_idx = i

        lcms_data = ma_data.df_container_from_metatlas_file(data[file_idx][compound_idx]['lcmsrun'].hdf5_file)

        #Find RT and mz peak for compound in file 
        rt_peak = data[file_idx][compound_idx]['data']['ms1_summary']['rt_peak']
        rt_peak_actual = lcms_data[lcms_polarity].iloc[(lcms_data[lcms_polarity].rt - rt_peak).abs().argsort()[0]].rt
        mz_peak_actual = data[file_idx][compound_idx]['data']['ms1_summary']['mz_peak']

        #Create and sort dataframe containing RT peak, mz and intensity
        df_all = lcms_data[lcms_polarity][(lcms_data[lcms_polarity].rt == rt_peak_actual)]
        df_all.sort_values('i',ascending=False,inplace=True)

        #Limit prior dataframe to +/- mz_min, mz_max
        df_window = df_all[(df_all['mz'] > mz_peak_actual - mz_min) &
                           (df_all['mz'] < mz_peak_actual + mz_max) ]
        
        #Plot compound name, mz, and RT peak
        plt.ioff()
        fig = plt.gcf()
        fig.suptitle('%s, m/z: %5.4f, rt: %f'%(all_compound_names[compound_idx], mz_peak_actual, rt_peak_actual),
                                                fontsize=8,weight='bold')

        #Create axes for different views of ms1 spectra (unscaled, scaled, and full range)
        ax1 = plt.subplot2grid((11, 12), (0, 0), rowspan=5, colspan=5)
        ax2 = plt.subplot2grid((11, 12), (0, 7), rowspan=5, colspan=5)
        ax3 = plt.subplot2grid((11, 12), (6, 0), rowspan=5, colspan=12)
        
        #Plot ms1 spectra
        for ax_idx,(ax,df) in enumerate(zip([ax1, ax2, ax3], [df_window, df_window, df_all])):

            ax.set_xlabel('m/z',fontsize=8,weight='bold')
            ax.set_ylabel('intensity',fontsize=8,weight='bold')
            ax.tick_params(axis='both', which='major', labelsize=6)
            ax.set_title(titles[ax_idx],fontsize=8,weight='bold')
            
            mzs = df['mz']
            zeros = np.zeros(len(df['mz']))
            intensities = df['i']
            
            ax.vlines(mzs, zeros, intensities, colors='r',linewidth = 2)

            labels = [1.001e9]
            for i,row in df.iloc[:6].iterrows():
                ax.annotate('%.4f'%row.mz, xy=(row.mz, 1.03*row.i),rotation = 90, horizontalalignment = 'center', verticalalignment = 'left', fontsize=6)
                labels.append(row.mz)

            ax.axhline(0)

            if ax_idx != 2:
                ax.set_xlim(mz_peak_actual - mz_min,  mz_peak_actual + mz_max)
                
            ylim = ax.get_ylim()
            
            if ax_idx == 1:                
                ax.set_ylim(ylim[0], df[((mz_peak_actual - .05 < df['mz']) & (df['mz'] < mz_peak_actual + .05))].iloc[0]['i']*1.43)
            else:
                ax.set_ylim(ylim[0], ylim[1]*1.43)

            if not os.path.exists(output_loc):
                os.makedirs(output_loc)

        plt.savefig(os.path.join(output_loc, all_compound_names[compound_idx] + '.pdf'))
            
            
def export_atlas_to_spreadsheet(myAtlas, output_filename='', input_type = 'atlas'):
    """
    Return a pandas dataframe containing Atlas info.  Optionally save it.
    This function can also work on a MetAtlas dataset (list of lists returned by get_data_for_atlas_and_groups).
    """
    cols = [c for c in metob.Compound.class_trait_names() if not c.startswith('_')]
    atlas_export = pd.DataFrame( )

    if input_type != 'atlas':
        num_compounds = len(myAtlas[0])
    else:
        num_compounds = len(myAtlas.compound_identifications)

    for i in range(num_compounds):
        if input_type != 'atlas':
            my_id = myAtlas[0][i]['identification']
            n = my_id.name
        else:
            my_id = myAtlas.compound_identifications[i]
   
        if my_id.compound:
            for c in cols:
                g = getattr(my_id.compound[0],c)
                if g:
                    atlas_export.loc[i,c] = g
        atlas_export.loc[i, 'label'] = my_id.name
        atlas_export.loc[i,'rt_min'] = my_id.rt_references[0].rt_min
        atlas_export.loc[i,'rt_max'] = my_id.rt_references[0].rt_max
        atlas_export.loc[i,'rt_peak'] = my_id.rt_references[0].rt_peak
        atlas_export.loc[i,'mz'] = my_id.mz_references[0].mz
        atlas_export.loc[i,'mz_tolerance'] = my_id.mz_references[0].mz_tolerance
        atlas_export.loc[i,'polarity'] = my_id.mz_references[0].detected_polarity
        if my_id.frag_references:
            atlas_export.loc[i,'has_fragmentation_reference'] = True
            # TODO: Gather the frag reference information and export it
        else:
            atlas_export.loc[i,'has_fragmentation_reference'] = False
    
    if output_filename:
        if not os.path.exists(os.path.dirname(output_filename)):
            os.makedirs(os.path.dirname(output_filename))
        atlas_export.to_csv(output_filename)

    return atlas_export
    
def get_data_for_groups_and_atlas(group,myAtlas,output_filename,use_set1 = False):
    """
    get and pickle everything This is MSMS, raw MS1 datapoints, compound, group info, and file info
    """
    data = []
    import copy as copy
    for i,treatment_groups in enumerate(group):
        for j in range(len(treatment_groups.items)):
            myFile = treatment_groups.items[j].hdf5_file
    #         try:
    #             rt_reference_index = int(treatment_groups.name[-1]) - 1
    #         except:
    #             rt_reference_index = 3
            print(i, len(group), myFile)
            row = []
            for compound in myAtlas.compound_identifications:
                result = {}
                result['atlas_name'] = myAtlas.name
                result['atlas_unique_id'] = myAtlas.unique_id
                result['lcmsrun'] = treatment_groups.items[j]
                result['group'] = treatment_groups
                temp_compound = copy.deepcopy(compound)
                if use_set1:
                    if '_Set1' in treatment_groups.name:
                        temp_compound.rt_references[0].rt_min -= 0.2
                        temp_compound.rt_references[0].rt_max -= 0.2
                        temp_compound.rt_references[0].rt_peak -= 0.2
                    temp_compound.mz_references[0].mz_tolerance = 20
                result['identification'] = temp_compound
                result['data'] = ma_data.get_data_for_a_compound(temp_compound.mz_references[0],
                                        temp_compound.rt_references[0],
                                        [ 'ms1_summary', 'eic', 'msms' ],
                                        myFile,0.2)
    #                 print result['data']['ms1_summary']
                row.append(result)
            data.append(row)
        with open(output_filename,'w') as f:
            dill.dump(data,f)

def filter_metatlas_objects_to_most_recent(object_list,field):
    #from datetime import datetime, date
    #remove from list if another copy exists that is newer
    unique_values = []
    for i,a in enumerate(object_list):
        unique_values.append( getattr(a,field) )
    unique_values = list(set(unique_values))
    keep_object_list = []
    for u in unique_values:
        old_last_modified = 0
        for i,a in enumerate(object_list):
            if getattr(a,field) == u:
                last_modified = getattr(a,'last_modified')
                if last_modified > old_last_modified:
                    keep_object = a
                    old_last_modified = last_modified
        keep_object_list.append(keep_object)
    return keep_object_list
#        print i, a.name,  datetime.utcfromtimestamp(a.last_modified)

def get_metatlas_atlas(name = '%%',username = '*', most_recent = True,do_print = True):
    from datetime import datetime, date
    atlas = metob.retrieve('Atlas',name = name,username=username)
    if most_recent:
        atlas = filter_metatlas_objects_to_most_recent(atlas,'name')
    if do_print:
        for i,a in enumerate(atlas):
            print(i, len(a.compound_identifications),a.name,  datetime.utcfromtimestamp(a.last_modified))

    return atlas

class interact_get_metatlas_files():
    def __init__(self, experiment = '%violacein%', name = '%_%', most_recent = True):
        self.experiment = experiment
        self.name = name
        self.most_recent = most_recent
#         http://ipywidgets.readthedocs.io/en/latest/examples/Using%20Interact.html
        self.w = interact(self.Task, experiment=self.experiment, name=self.name, most_recent = self.most_recent,__manual=True)#continuous_update=False)#
       
    def Task(self,experiment,name,most_recent):
        self.experiment = experiment
        self.name = name
        self.most_recent = most_recent
        self.files = get_metatlas_files(experiment = experiment,name = name,most_recent = most_recent)#self.most_recent)
        txt = widgets.Text()
        txt.value = '%d Files were found matching that pattern'%len(self.files)
        display(txt)



def get_metatlas_files(experiment = '%%',name = '%%',most_recent = True):
    """
    experiment is the folder name
    name is the filename
    """
    files = metob.retrieve('LcmsRun',experiment=experiment,name=name, username='*')
    if most_recent:
        files = filter_metatlas_objects_to_most_recent(files,'mzml_file')
    return files

def make_empty_fileinfo_sheet(filename,flist):
    #dump all the files to a spreadheet, download it, and make a "filled in" one.
    with open(filename,'w') as fid:
        fid.write('mzml_file\tgroup\tdescription\n')
        for f in flist:
            fid.write('%s\t\t\n'%f.mzml_file)

def make_groups_from_fileinfo_sheet(filename,filetype='tab',store=False):
    '''
    
    '''
    if filetype == 'tab':
        df = pd.read_csv(filename,sep='\t')
    elif filetype == 'csv':
        df = pd.read_csv(filename,sep=',')
    else:
        df = pd.read_excel(filename)
    grouped = df.groupby(by='group')
    return_groups = []
    for g in grouped.groups.keys():
        indices = grouped.groups[g]
        myGroup = metob.Group()
        myGroup.name = '%s'%g
        myGroup.description = df.loc[indices[0],'description']
        file_set = []
        for i in indices:
            file_set.append(metob.retrieve('LcmsRun',mzml_file='%%%s'%df.loc[i,'mzml_file'],username='*')[0])
        myGroup.items = file_set
        return_groups.append(myGroup)
        if store:
            metob.store(myGroup)
    return return_groups
            
    
    
def check_compound_names(df):
    # compounds that have the wrong compound name will be listed
    # Keep running this until no more compounds are listed
    bad_names = []
    for i,row in df.iterrows():
        #if type(df.name[x]) != float or type(df.label[x]) != float:
            #if type(df.name[x]) != float:
        if not pd.isnull(row.inchi_key):# or type(df.inchi_key[x]) != float:
            if not metob.retrieve('Compounds',inchi_key=row.inchi_key, username = '*'):
                print(row.inchi_key, "compound is not in database. Exiting Without Completing Task!")
                bad_names.append(row.inchi_key)
    return bad_names


def check_file_names(df,field):
    bad_files = []
    for i,row in df.iterrows():
        if row[field] != '':
            if not metob.retrieve('Lcmsruns',name = '%%%s%%'%row[field],username = '*'):
                print(row[field], "file is not in the database. Exiting Without Completing Task!")
                bad_files.append(row[field])
    return bad_files


def get_formatted_atlas_from_google_sheet(polarity='POS',
                                          method='QE_HILIC',
                                          mz_tolerance=10):
    import metatlas.ms_monitor_util as mmu
    df2 = mmu.get_ms_monitor_reference_data()
    #print df.head()
    #df2 = pd.DataFrame(df[1:],columns=df[0])

    fields_to_keep = [ 'name',
                    'label',
                      'inchi_key',
                    'mz_%s'%polarity,
                    'rt_min_%s'%method,
                    'rt_max_%s'%method,
                    'rt_peak_%s'%method,
                    'file_mz_%s_%s'%(method,polarity),
                    'file_rt_%s_%s'%(method,polarity),
                    'file_msms_%s_%s'%(method,polarity)]
    
    fields_there = []
    for f in fields_to_keep:
         if f in df2.keys():
                fields_there.append(f)
    
    df3 = df2.loc[:,fields_there]
    
    df3['mz_tolerance'] = mz_tolerance

    if polarity == 'POS':
        df3['polarity'] = 'positive'
    else:
        df3['polarity'] = 'negative'

    renamed_columns = [c.replace('_%s'%method,'').replace('_%s'%polarity,'') for c in df3.columns]
    for i,c in enumerate(df3.columns):
        df3 = df3.rename(columns = {c:renamed_columns[i]})
    df3 = df3[df3['mz'] != '']

    return df3


def make_atlas_from_spreadsheet(filename='valid atlas file.csv',
                                atlas_name='20161007_MP3umZHILIC_BPB_NEG_ExampleAtlasName',
                                filetype=('excel','csv','tab','dataframe'),
                                sheetname='only for excel type input',
                                polarity = ('positive','negative'),
                                store=False,
                                mz_tolerance=10):
    '''
    specify polarity as 'positive' or 'negative'
    
    '''
    if isinstance(filename,pd.DataFrame):
        df = filename
    else:
        if ( filetype=='excel' ) and sheetname:
            df = pd.read_excel(filename,sheetname=sheetname)
        elif ( filetype=='excel' ):
            df = pd.read_excel(filename)
        elif filetype == 'tab':
            df = pd.read_csv(filename,sep='\t')
        else:
            df = pd.read_csv(filename,sep=',')
    df.dropna(how="all", inplace=True)
    df.columns = [x.lower() for x in df.columns]

    bad_names = check_compound_names(df)
    if bad_names:
        return bad_names
    #Make sure all the files specified for references are actually there
    #if 'file_rt' in df.keys():
        #strip '.mzmL' from cells
        #df.file_rt = df.file_rt.str.replace('\..+', '')
        #bad_files = check_file_names(df,'file_rt')
        #if bad_files:
        #     return bad_files
    #if 'file_mz' in df.keys():
    #    #strip '.mzmL' from cells
    #    df.file_mz = df.file_mz.str.replace('\..+', '')
    #    bad_files = check_file_names(df,'file_mz')
    #    if bad_files:
    #         return bad_files
    if 'file_msms' in df.keys():
        #strip '.mzmL' from cells
        df.file_msms = df.file_msms.str.replace('\..+', '')
        bad_files = check_file_names(df,'file_msms')
        if bad_files:
             return bad_files
    

    
    all_identifications = []

#     for i,row in df.iterrows():
    for i,row in df.iterrows():
        if type(row.inchi_key) != float or type(row.label) != float: #this logic is to skip empty rows
            
            myID = metob.CompoundIdentification()
            
            if not pd.isnull(row.inchi_key): # this logic is where an identified metabolite has been specified
                c = metob.retrieve('Compounds',neutralized_inchi_key=row.inchi_key,username = '*') #currently, all copies of the molecule are returned.  The 0 is the most recent one. 
                if c:
                    c = c[0]
            else:
                c = 'use_label'
            if type(row.label) != float:
                compound_label = row.label #if no name, then use label as descriptor
            else:
                compound_label = 'no label'
            
            if c:
                if c != 'use_label':
                    myID.compound = [c]
                myID.name = compound_label
                
                
                mzRef = metob.MzReference()
                # take the mz value from the spreadsheet
                mzRef.mz = row.mz
                #TODO: calculate the mz from theoretical adduct and modification if provided.
                #     mzRef.mz = c.MonoIso topic_molecular_weight + 1.007276
                if mz_tolerance:
                    mzRef.mz_tolerance = mz_tolerance
                else:
                    try:
                        mzRef.mz_tolerance = row.mz_tolerance
                    except:
                        mzRef.mz_tolerance = row.mz_threshold    
                
                mzRef.mz_tolerance_units = 'ppm'
                mzRef.detected_polarity = polarity
                #if 'file_mz' in df.keys():
                #    f = metob.retrieve('Lcmsruns',name = '%%%s%%'%df.file_mz[x],username = '*')[0]
                #    mzRef.lcms_run = f
                #     mzRef.adduct = '[M-H]'   
                myID.mz_references = [mzRef]

                rtRef = metob.RtReference()
                rtRef.rt_units = 'min'
                rtRef.rt_min = row.rt_min
                rtRef.rt_max = row.rt_max
                rtRef.rt_peak = row.rt_peak
                #if 'file_rt' in df.keys():
                #    f = metob.retrieve('Lcmsruns',name = '%%%s%%'%df.file_rt[x],username = '*')[0]
                #    rtRef.lcms_run = f
                myID.rt_references = [rtRef]
                    
                if ('file_msms' in df.keys()) and (c != 'use_label'):
                    if (type(row.file_msms) != float) and (row.file_msms != ''):
                        frag_ref = metob.FragmentationReference()
                        f = metob.retrieve('Lcmsruns',name = '%%%s%%'%row.file_msms,username = '*')[0]
                        frag_ref.lcms_run = f
                        frag_ref.polarity = polarity
                        frag_ref.precursor_mz = row.mz
                        
                        data = ma_data.get_data_for_a_compound(mzRef, rtRef, [ 'msms' ],f.hdf5_file,0.3)
                        if isinstance(data['msms']['data'], np.ndarray):
                            precursor_intensity = data['msms']['data']['precursor_intensity']
                            idx_max = np.argwhere(precursor_intensity == np.max(precursor_intensity)).flatten() 
                            mz = data['msms']['data']['mz'][idx_max]
                            intensity = data['msms']['data']['i'][idx_max]
                            spectrum = []
                            for i in range(len(mz)):
                                mzp = metob.MzIntensityPair()
                                mzp.mz = mz[i]
                                mzp.intensity = intensity[i]
                                spectrum.append(mzp)
                            frag_ref.mz_intensities = spectrum
                            myID.frag_references = [frag_ref]
                            print('')
                            print('found reference msms spectrum for ',myID.compound[0].name, 'in file',row.file_msms)

                all_identifications.append(myID)

    myAtlas = metob.Atlas()
    myAtlas.name = atlas_name
    myAtlas.compound_identifications = all_identifications
    if store:
        metob.store(myAtlas)
    return myAtlas

def filter_empty_metatlas_objects(object_list,field):
    filtered_list = []
    for i,g in enumerate(object_list):
        try:
            #This bare try/accept is to handle the invalid groups left over in the database from the original objects.
            #These groups don't conform to the current schema and will throw an error when you query their attributes.
            if (len(getattr(g,field)) > 0):
                filtered_list.append(g)
        except:
            pass
    return filtered_list

def filter_metatlas_objects_by_list(object_list,field,filter_list):
    filtered_list = []
    for i,g in enumerate(object_list):
        if any(ext in getattr(g,field) for ext in filter_list):
            filtered_list.append(g)
    return filtered_list

def remove_metatlas_objects_by_list(object_list,field,filter_list):
    filtered_list = []
    for i,g in enumerate(object_list):
        if not any(ext in getattr(g,field) for ext in filter_list):
            filtered_list.append(g)
    return filtered_list

def filter_lcmsruns_in_dataset_by_include_list(metatlas_dataset,selector,include_list):
    """
    Returns a metatlas dataset containing LCMS runs or groups (denoted by selector) that have substrings listed in the include list
    selector can be 'lcmsrun' or 'group'
    include_list will look something like this: ['QC','Blank']
    """
    filtered_dataset = []
    for d in metatlas_dataset:
        if any(ext in d[0][selector].name for ext in include_list):
            filtered_dataset.append(d)
    return filtered_dataset

def filter_lcmsruns_in_dataset_by_exclude_list(metatlas_dataset,selector,exclude_list):
    """
    Returns a metatlas dataset containing LCMS runs or groups (denoted by selector) that have substrings not listed in the include list
    selector can be 'lcmsrun' or 'group'
    exclude_list will look something like this: ['QC','Blank']
    """
    filtered_dataset = []
    for d in metatlas_dataset:
        if not any(ext in d[0][selector].name for ext in exclude_list):
            filtered_dataset.append(d)
    return filtered_dataset


def filter_compounds_in_dataset_by_exclude_list(metatlas_dataset,exclude_list):
    """
    Since the rows of the dataset are expected to line up with an atlas export, this is probably not a good idea to use.
    """
    filtered_dataset = []
    for d_row in metatlas_dataset:
        filtered_row = []
        for d in d_row:
            if not any(ext in d['identification'].name for ext in exclude_list):
                if not any(ext in d['identification'].compound[0].name for ext in exclude_list):
                    filtered_row.append(d)
        filtered_dataset.append(filtered_row)
    return filtered_dataset

def filter_compounds_in_dataset_by_include_list(metatlas_dataset,include_list):
    """
    Since the rows of the dataset are expected to line up with an atlas export, this is probably not a good idea to use.
    """
    filtered_dataset = []
    for d_row in metatlas_dataset:
        filtered_row = []
        for d in d_row:
            if any(ext in d['identification'].name for ext in include_list):
                if any(ext in d['identification'].compound[0].name for ext in include_list):
                    filtered_row.append(d)
        filtered_dataset.append(filtered_row)
    return filtered_dataset
      
def select_groups_for_analysis(name = '%', description = [], username = '*', do_print = True, most_recent = True, remove_empty = True, include_list = [], exclude_list = []):
    if description:
        groups = metob.retrieve('Groups', name = name, description = description, username=username)
    else:
        groups = metob.retrieve('Groups', name = name, username=username)
    if most_recent:
        groups = filter_metatlas_objects_to_most_recent(groups,'name')
    
    if include_list:
        groups = filter_metatlas_objects_by_list(groups,'name',include_list)
        
    if exclude_list:
        groups = remove_metatlas_objects_by_list(groups,'name',exclude_list)

    print(len(groups))

    if remove_empty:
        groups = filter_empty_metatlas_objects(groups,'items')
    if do_print:
        from datetime import datetime, date
        for i,a in enumerate(groups):
            print(i, a.name,  datetime.utcfromtimestamp(a.last_modified))

    return groups



# 