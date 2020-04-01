# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class IacPartClass(models.Model):
    """材料大类
        1级材料类别
    """
    _name = "iac.part.class"
    _description = "Part Class"

    name = fields.Char(string="Part Class", required=True, help=u'材料大类名称')
    description = fields.Char(string="Description")

class IacPartCategory(models.Model):
    """
    材料类别资料，一个材料大类part_class拥有多个材料类别，材料大类part_class直接用Selection类型
    2级材料类别
    """
    _name = "iac.part.category"
    _description = "Part Category"

    name = fields.Char(string="Part Category", required=True, help=u'材料类别名称')
    part_class = fields.Many2one('iac.part.class', string='Part Class', required=True, help=u'材料大类')
    material_group_ids = fields.Many2many("material.group", 'part_category_material_groups',
        'part_category_id', 'material_group_id', string="Material Group")

class IacPartCategoryMaterialGroupHistory(models.Model):
    """
    part_category_material_groups历史表，自动产生待评核Vendor前备份
    """
    _name = "iac.part_category.material_group.history"
    _description = "Score Part Category and Material Group History"

    part_category_id = fields.Many2one('iac.part.category', string="Part Category", required=True)
    material_group_id = fields.Many2one("material.group", string="Material Group", required=True)
    score_snapshot = fields.Char(string='Score Snapshot')# 识别快照号，以%Y-%m-%d作为取值依据

class IacScoreIqcMprma(models.Model):
    """
    评分区间 vs_iqc_mprma
    """
    _name = "iac.score.iqc.mprma"
    _description = "Vendor Score IQC MPRMA"

    part_category_id = fields.Many2one('iac.part.category', string="Part Category", required=True)
    score_type = fields.Selection(string='Score Type', selection='_selection_score_type', required=True)
    score = fields.Float(string='Score', required=True, digits=(7, 2))
    lower_limit = fields.Float(string='Lower Limit', required=True, digits=(7, 4))
    high_limit = fields.Float(string='High Limit', required=True, digits=(7, 4))

    @api.model
    def _selection_score_type(self):
        res_type = []
        type_list = self.env['ir.config_parameter'].search([('key', 'like', 'score_score_type_')])
        for item in type_list:
            res_type.append((item.key[17:], _(item.value)))

        return res_type

class IacScoreIqcMprmaHistory(models.Model):
    """
    评分区间历史表 vs_iqc_mprma_history
    """
    _name = "iac.score.iqc.mprma.history"
    _description = "Vendor Score IQC MPRMA History"

    part_category_id = fields.Many2one('iac.part.category', string="Part Category", required=True)
    score_type = fields.Selection(string='Score Type', selection='_selection_score_type', required=True)
    score = fields.Float(string='Score', required=True, digits=(7, 2))
    lower_limit = fields.Float(string='Lower Limit', required=True, digits=(7, 4))
    high_limit = fields.Float(string='High Limit', required=True, digits=(7, 4))
    score_snapshot = fields.Char(string='Score Snapshot')  # 识别快照号，以%Y-%m-%d作为取值依据

    @api.model
    def _selection_score_type(self):
        res_type = []
        type_list = self.env['ir.config_parameter'].search([('key', 'like', 'score_score_type_')])
        for item in type_list:
            res_type.append((item.key[17:], _(item.value)))

        return res_type

class IacFailCostSection(models.Model):
    """
    失败成本区间 Vs_Fail_Cost
    """
    _name = "iac.fail.cost.section"
    _description = "Fail Cost Section"

    fail_type = fields.Selection(string='Score Type', selection='_selection_fail_type', required=True)
    score = fields.Float(string='Score', required=True, digits=(7, 2))
    lower_limit = fields.Float(string='Lower Limit', required=True, digits=(7, 2))
    high_limit = fields.Float(string='High Limit', required=True, digits=(7, 2))

    @api.model
    def _selection_fail_type(self):
        res_type = []
        type_list = self.env['ir.config_parameter'].search([('key', 'like', 'score_fail_type_')])
        for item in type_list:
            res_type.append((item.key[16:], _(item.value)))

        return res_type

class IacFailCostSectionHistory(models.Model):
    """
    失败成本区间 Vs_Fail_Cost_History
    """
    _name = "iac.fail.cost.section.history"
    _description = "Fail Cost Section History"

    fail_type = fields.Selection(string='Score Type', selection='_selection_fail_type', required=True)
    score = fields.Float(string='Score', required=True, digits=(7, 2))
    lower_limit = fields.Float(string='Lower Limit', required=True, digits=(7, 2))
    high_limit = fields.Float(string='High Limit', required=True, digits=(7, 2))
    score_snapshot = fields.Char(string='Score Snapshot')  # 识别快照号，以%Y-%m-%d作为取值依据

    @api.model
    def _selection_fail_type(self):
        res_type = []
        type_list = self.env['ir.config_parameter'].search([('key', 'like', 'score_fail_type_')])
        for item in type_list:
            res_type.append((item.key[16:], _(item.value)))

        return res_type

class IacVendorScorePlant(models.Model):
    """
    用于记录同一个site的评核名单，用于给SCM Controller和QM Controller发送邮件
    """
    _name = 'iac.score.plant'

    plant_id = fields.Many2one('pur.org.data', string="Plant")
    scm_controller_id = fields.Many2one('res.partner', string="SCM Controller", domain="[('supplier','=',False)]")
    qm_controller_id = fields.Many2one('res.partner', string="QM Controller", domain="[('supplier','=',False)]")
    list_ids = fields.One2many('iac.score.list', 'score_plant_id', string="Score List")
    score_snapshot = fields.Char(string='Score Snapshot')  # 识别快照号，标记使用的哪个材料类别/评分区间/失败成本区间的快照

class IacVendorScoreExclude(models.Model):
    """
    免评Supplier Company vs_exclude_sc
    """
    _name = 'iac.score.exclude'
    _description = "Exclude Vendor"

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    active = fields.Boolean('Active', default=True,
        help="If unchecked, it will allow you to hide the definition without removing it.")
    memo = fields.Text(string="Memo")

class IacVendorScoreDefinition(models.Model):
    """
    Vendor评鉴定义，评核设定档 vscore_definition
    """
    _name = 'iac.score.definition'
    _description = "Vendor Score Definition"
    _order = 'group_code,seq_no'

    code = fields.Char(string="Code", readonly=True)
    group_code = fields.Selection([
        ('SCM', 'SCM'),
        ('QM', 'QM')], string="Group")
    seq_no = fields.Integer(string="Sequence")
    display_label = fields.Char(string="Display Label")
    description = fields.Char(string="Description", help=u"评分项目")
    score_standard = fields.Char(string="Score Standard", help=u"评分标准")
    ratio = fields.Integer(string="Weight", help=u"权重")
    memo = fields.Text(string="Memo")
    active = fields.Boolean(
        'Active', default=True,
        help="If unchecked, it will allow you to hide the definition without removing it.")
    part_class = fields.Many2one('iac.part.class', string='Part Class', help=u"材料大类")

    @api.model
    def create(self, values):
        values['code'] = values['group_code'] . self.env['ir.sequence'].next_by_code('score.definition.code')
        return super(IacVendorScoreDefinition, self).create(values)

class IacVendorScoreRange(models.Model):
    """
    score_range 评分参考区间
    """
    _name = 'iac.score.range'
    _description = "Vendor Score Range"
    _order = 'log_type,range_from'

    log_type = fields.Char(string="Log Type")
    level_t = fields.Char(string="Level")
    range_from = fields.Float(string="Range From", digits=(14, 3))
    range_to = fields.Float(string="Range To", digits=(14, 3))
    score = fields.Float(string="Score", digits=(6, 1))