# -*- coding: utf-8 -*-

from odoo import api, fields, models,tools


class IacCollectMaterial(models.Model):
    _name = "v.collect.material"
    _auto = False

    delivery_no = fields.Char()
    memo = fields.Char()
    g_no = fields.Char()
    cop_g_no = fields.Char()
    hscode = fields.Char()
    g_name = fields.Char()
    qty_1 = fields.Float()
    unit = fields.Char()
    description = fields.Char()
    pur_code = fields.Char()
    pur_name = fields.Char()
    ems_type = fields.Char()
    manufacturer_name = fields.Char()
    vendor_code = fields.Char()
    transit_time = fields.Datetime()
    status = fields.Char()
    auto_no = fields.Char()
    statustax = fields.Char()

    @api.model_cr
    def init(self):
        tools.drop_view_if_exists(self._cr, 'v_collect_material')
        self._cr.execute("""
CREATE OR REPLACE VIEW public.v_collect_material
AS SELECT icsh.sas_stock_no AS delivery_no,
    cph.pass_port_no AS memo,
    csl.oriact_gds_seqno::character varying AS g_no,
    csl.gds_mtno AS cop_g_no,
    csl.gdecd AS hscode,
    csl.gds_nm AS g_name,
    csl.dcl_qty AS qty_1,
    csl.dcl_unitcd AS unit,
    mm.part_description AS description,
    mm.buyer_erp_id AS pur_code,
    bc.buyer_name AS pur_name,
    csdl.mtpck_endprd_typecd AS ems_type,
    iv.name AS manufacturer_name,
    iv.vendor_code,
    cph.pass_time AS transit_time,
    cph.stucd AS status,
    cph.vehicle_no AS auto_no,
    cz.para_description AS statustxt,
    sla.storage_location,
    pod.plant_code
   FROM iac_customs_sas_header icsh
     JOIN iac_customs_pass_port_header cph ON icsh.pass_port_id = cph.id
     JOIN pur_org_data pod ON icsh.plant_id = pod.id
     JOIN iac_customs_sas_line csl ON icsh.id = csl.sas_stock_id
     JOIN iac_customs_sas_declare csd ON csd.id = icsh.sas_dcl_id
     JOIN iac_customs_sas_declare_line csdl ON csdl.header_id = icsh.sas_dcl_id AND csdl.id = csl.sas_dcl_line_id
     JOIN material_master mm ON csl.part_id = mm.id
     JOIN buyer_code bc ON mm.buyer_code_id = bc.id
     JOIN iac_vendor iv ON icsh.vendor_id = iv.id
     LEFT JOIN iac_storage_location_address sla ON icsh.storage_location_id = sla.id
     LEFT JOIN iac_customs_zparameters cz ON cph.stucd::text = cz.para_key_value::text AND cz.para_category::text = '海关状态'::text;
""")