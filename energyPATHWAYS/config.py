__author__ = 'Ben Haley & Ryan Jones'

import ConfigParser
import os
import warnings
from collections import defaultdict

import pandas as pd
import pint
import psycopg2

import geography
import util
import data_models.data_source as data_source

#import ipdb

# Don't print warnings
warnings.simplefilter("ignore")

# directory = None
weibul_coeff_of_var = None
cfgfile = None
primary_geography = None

# db connection and cursor
con = None
cur = None

# common data inputs
dnmtr_col_names = ['driver_denominator_1_id', 'driver_denominator_2_id']
drivr_col_names = ['driver_1_id', 'driver_2_id']

# Initiate pint for unit conversions
ureg = None

##Geography conversions
geo = None

# output config
currency_name = None
output_levels = None
outputs_id_map = None
output_currency = None

# for dispatch
electricity_energy_type_id = None
electricity_energy_type_shape_id = None

def initialize_config(cfgfile_path, custom_pint_definitions_path):
    # sys.path.insert(0, os.getcwd())
    # global directory
    # directory = os.getcwd().rstrip('code')
    # weibul_coefficient_of_variation is used to find weibul parameters given lifetime statistics
    global weibul_coeff_of_var
    weibul_coeff_of_var = util.create_weibul_coefficient_of_variation()
    init_cfgfile(cfgfile_path)
    # TODO: this requires the cfg global to be assigned to a config object but note that it is in the constructor. Thus the global assignment above. Yuck.
    init_db()
    init_pint(custom_pint_definitions_path)
    init_geo()
    init_electricity_energy_type()
    init_outputs_id_map()

def load_config(cfgfile_path):
    global cfgfile
    cfgfile = ConfigParser.ConfigParser()
    cfgfile.read(cfgfile_path)

def init_cfgfile(cfgfile_path):
    load_config(cfgfile_path)
    global primary_geography
    #if not os.path.isfile(cfgfile_path):
    #    raise OSError('config file not found: ' + str(cfgfile_path))
    
    
    
    # cfgfile.add_section('directory')
    # cfgfile.set('directory', 'path', directory)
    cfgfile.set('case', 'years', range(int(cfgfile.get('case', 'start_year')),
                                       int(cfgfile.get('case', 'end_year')) + 1,
                                       int(cfgfile.get('case', 'year_step'))))
    cfgfile.set('case', 'supply_years', range(int(cfgfile.get('case', 'current_year')),
                                              int(cfgfile.get('case', 'end_year')) + 1,
                                              int(cfgfile.get('case', 'year_step'))))

    primary_geography = cfgfile.get('case', 'primary_geography')
        
def init_db():
    global con, cur, dnmtr_col_names, drivr_col_names
    pg_host = cfgfile.get('database', 'pg_host')
    if not pg_host:
        pg_host = 'localhost'
    pg_user = cfgfile.get('database', 'pg_user')
    pg_password = cfgfile.get('database', 'pg_password')
    pg_database = cfgfile.get('database', 'pg_database')
    conn_str = "host='%s' dbname='%s' user='%s'" % (pg_host, pg_database, pg_user)
    if pg_password:
        conn_str += " password='%s'" % pg_password

    global dbCfg
    dbCfg = {
      'drivername': 'postgres',
      'host':       pg_host,
      'port':       '5432',
      'username':   pg_user,
      'password':   pg_password,
      'database':   pg_database
    }
    data_source.init(dbCfg)

    # Open pathways database
    con = psycopg2.connect(conn_str)
    cur = con.cursor()

def init_pint(custom_pint_definitions_path=None):
    # Initiate pint for unit conversions
    global ureg
    ureg = pint.UnitRegistry()
    
    if custom_pint_definitions_path is not None:
        if not os.path.isfile(custom_pint_definitions_path):
            raise OSError('pint definitions file not found: ' + str(custom_pint_definitions_path))
        ureg.load_definitions(custom_pint_definitions_path)

def init_geo():
    #Geography conversions
    global geo
    geo = geography.Geography()

def init_electricity_energy_type():
    global electricity_energy_type_id, electricity_energy_type_shape_id
    electricity_energy_type_id, electricity_energy_type_shape_id = util.sql_read_table('FinalEnergy', column_names=['id', 'shape_id'], name='electricity')

def init_outputs_id_map():
    global currency_name, output_levels, outputs_id_map, output_currency
    currency_name = util.sql_read_table('Currencies', 'name', id=int(cfgfile.get('case', 'currency_id')))
    output_levels = cfgfile.get('case', 'output_levels').split(', ')
    output_currency = cfgfile.get('case', 'currency_year_id') + ' ' + currency_name
    outputs_id_map = defaultdict(dict)
    if 'primary_geography' in output_levels:
        output_levels[output_levels.index('primary_geography')] = primary_geography
    primary_geography_id = util.sql_read_table('Geographies', 'id', name=primary_geography)
    print primary_geography_id
    outputs_id_map[primary_geography] = util.upper_dict(util.sql_read_table('GeographiesData', ['id', 'name'], geography_id=primary_geography_id, return_unique=True, return_iterable=True))
    outputs_id_map[primary_geography+"_supply"] =  outputs_id_map[primary_geography]       
    outputs_id_map['technology'] = util.upper_dict(util.sql_read_table('DemandTechs', ['id', 'name']))
    outputs_id_map['final_energy'] = util.upper_dict(util.sql_read_table('FinalEnergy', ['id', 'name']))
    outputs_id_map['supply_node'] = util.upper_dict(util.sql_read_table('SupplyNodes', ['id', 'name']))       
    outputs_id_map['supply_node_export'] = util.upper_dict(util.sql_read_table('SupplyNodes', ['id', 'name'])," EXPORT")
    outputs_id_map['subsector'] = util.upper_dict(util.sql_read_table('DemandSubsectors', ['id', 'name']))           
    outputs_id_map['sector'] = util.upper_dict(util.sql_read_table('DemandSectors', ['id', 'name']))
    outputs_id_map['ghg'] = util.upper_dict(util.sql_read_table('GreenhouseGases', ['id', 'name']))
    for id, name in util.sql_read_table('OtherIndexes', ('id', 'name'), return_iterable=True):
        if name in ('technology', 'final_energy'): 
            continue
        outputs_id_map[name] = util.upper_dict(util.sql_read_table('OtherIndexesData', ['id', 'name'], other_index_id=id, return_unique=True))
