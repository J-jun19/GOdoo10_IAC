# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError



class IacAsnMaxQtyLog(models.Model):
    _name = 'iac.asn.max.qty.log'
    _order = 'id desc'
    shipped_qty =fields.Integer('Shipped QTY',default=0)
    file_line_no=fields.Integer(string='File Line No')
    state=fields.Selection([('cancel','Cancel'),('done','Done')],string='State',default='done')
    last_max_qty_id=fields.Many2one('asn.maxqty',string='Last Max Qty')
    comments=fields.Text(string="Comments")
    version = fields.Char(string="Version")
    vendorcode = fields.Char(string="Vendorcode",index=True)
    plant = fields.Char(string="Plant",index=True)
    material = fields.Char(string="Material",index=True)
    deliverytype = fields.Char(string="Deliverytype")
    maxqty = fields.Integer(string="Maxqty")
    engineid = fields.Selection([("IACD","IACD"),("IACW","IACW")],string="Engineid")
    createdate = fields.Date(string="Createdate")
    division = fields.Char(string="Division",index=True)

    #lwt add relation fields
    division_id=fields.Many2one('division.code',string='Division Info')
    part_id = fields.Many2one('material.master', string='Part No')
    vendor_id = fields.Many2one('iac.vendor', string="Vendor Info")
    vendor_reg_id = fields.Many2one('iac.vendor.register', string="Vendor Registration")
    plant_id = fields.Many2one('pur.org.data', 'Plant')
    sap_log_id = fields.Char(string="Sap log Info",index=True)
    sap_temp_id = fields.Integer(string="Sap Temp Info",index=True)
    asn_increase_line_ids=fields.One2many('iac.asn.max.qty.log.line','asn_max_qty_id',string='ASN Increase QTY Info')


class IacAsnMaxQtyCreateLine(models.Model):
    _name="iac.asn.max.qty.log.line"
    _order = 'id desc'

    plant_id = fields.Many2one('pur.org.data', string='Plant Info')
    vendor_id = fields.Many2one('iac.vendor', string='Vendor Info')
    part_id = fields.Many2one('material.master', string='Part No')
    increase_qty =fields.Integer('Increase QTY',default=0)
    asn_max_qty_id = fields.Many2one('iac.asn.max.qty.log', string='ASN MAX QTY ID')
    comments=fields.Text(string="Comments")