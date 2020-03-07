# -*- coding: utf-8 -*-

from odoo import fields,models

class PlantLocationCodeMapping(models.Model):

    _name = 'plant.location.code.mapping'

    plant_code = fields.Char()
    storage_location = fields.Char()
    plant_code_mapping = fields.Char()  #plant对应的编码
    storage_location_mapping = fields.Char() #location对应的编码

