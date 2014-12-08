# -*- coding: utf-8 -*-

{
    'name': 'Fleet Management',
    'version': '0.1',
    'author': 'Odoo S.A.',
    'sequence': 110,
    'category': 'Managing vehicles and contracts',
    'website': 'https://www.odoo.com/page/fleet',
    'summary': 'Vehicle, leasing, insurances, costs',
    'description': """
Vehicle, leasing, insurances, cost
==================================
With this module, OpenERP helps you managing all your vehicles, the
contracts associated to those vehicle as well as services, fuel log
entries, costs and many other features necessary to the management 
of your fleet of vehicle(s)

Main Features
-------------
* Add vehicles to your fleet
* Manage contracts for vehicles
* Reminder when a contract reach its expiration date
* Add services, fuel log entry, odometer values for all vehicles
* Show all costs associated to a vehicle or to a type of service
* Analysis graph for costs
""",
    'depends': [
        'base',
        'mail',
        'board'
    ],
    'data': [
        'security/fleet_security.xml',
        'security/ir.model.access.csv',
        'views/fleet_view.xml',
        'views/fleet_board_view.xml'
    ],
    'images': ['images/costs_analysis.jpeg','images/indicative_costs_analysis.jpeg','images/vehicles.jpeg','images/vehicles_contracts.jpeg','images/vehicles_fuel.jpeg','images/vehicles_odometer.jpeg','images/vehicles_services.jpeg'],

    'demo': [
        'data/fleet_cars.xml',
        'data/fleet_data.xml',
        'data/fleet_demo.xml'
    ],

    'installable': True,
    'application': True,
}
