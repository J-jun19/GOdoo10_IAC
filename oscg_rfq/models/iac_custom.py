# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools
from odoo.tools.translate import _
from odoo.http import request
import datetime

class IacCustomDataUnfinished(models.Model):

    _name = 'iac.custom.data.unfinished.pub'

    delivery = fields.Char()
    item_no = fields.Char()
    part_no = fields.Char()
    part_id = fields.Many2one('material.master')
    vendor_code = fields.Char()
    vendor_id = fields.Many2one('iac.vendor')
    manu_no = fields.Char()
    manu_name = fields.Char()
    transit_time = fields.Datetime()
    last_entry_time = fields.Datetime()
    g_name = fields.Char()
    quantity_in = fields.Float()
    amount = fields.Float()
    units = fields.Char()
    g_no = fields.Char()
    versions = fields.Char()
    quantity_back = fields.Float()
    sku = fields.Char()
    additional_code = fields.Char()
    description = fields.Char()
    entry_apply_no = fields.Char()
    pre_entry_no = fields.Char()


class IacCustomVendorVSSapVendor(models.Model):

    _name = 'iac.custom.vendor.vs.sap.vendor.pub'

    plant = fields.Char()
    vendor_code = fields.Char()
    manu_no = fields.Char()
    plant_id = fields.Many2one('pur.org.data')
    vendor_id = fields.Many2one('iac.vendor')