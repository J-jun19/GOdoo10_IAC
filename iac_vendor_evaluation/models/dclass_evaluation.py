# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class IacVendorDClassPartCategoryScmUser(models.Model):
    """SCM User 选择 D Class处理方式"""
    _name = 'iac.dclass.part_category.scm_user'
    _inherit = 'iac.class.part_category'
    _table = 'iac_class_part_category'

    # @api.multi
    # def action_batch_d_class_submit(self):
    #     """
    #     选择处理方式后提交
    #     :return:
    #     """
    #     for class_part_category_id in self:
    #         if not class_part_category_id.dclass_type:
    #             raise UserError(_(u'请选择D Class 处理方式。'))
    #         if not class_part_category_id.dclass_file_id:
    #             raise UserError(_(u'请上传D Class文件。'))
    #
    #         if class_part_category_id.state == 'd class':
    #             if class_part_category_id.dclass_type == 'special.release':
    #                 class_part_category_id.state = 'to qm controller approve'
    #             else:
    #                 class_part_category_id.state = 'to scm leader approve'
    #
    #         return self.env['warning_box'].info(title=u"提示信息", message=u"提交成功！")

class IacVendorDClassPartCategoryScmController(models.Model):
    """SCM Controller 评定 Class"""
    _name = 'iac.dclass.part_category.scm_controller'
    _inherit = 'iac.class.part_category'
    _table = 'iac_class_part_category'

class IacVendorDClassPartCategoryScmLeader(models.Model):
    _name = 'iac.dclass.part_category.scm_leader'
    _inherit = 'iac.class.part_category'
    _table = 'iac_class_part_category'

    # @api.multi
    # def action_batch_d_class_scm_leader_approve(self):
    #     """
    #     SCM Leader审核可採購/不能建BOM(PNRF)、不可採購/不能建BOM (CEO零件停產執行單)，通过
    #     :return:
    #     """
    #     for class_part_category_id in self:
    #         if class_part_category_id.state == 'to scm leader approve':
    #             class_part_category_id.state = 'd done'
    #             super(IacVendorDClassPartCategoryScmLeader, self).gen_supplier_company_class(class_part_category_id)
    #
    #         return self.env['warning_box'].info(title=u"提示信息", message=u"审核完成！")

    # @api.multi
    # def action_batch_d_class_scm_leader_disapprove(self):
    #     """
    #     SCM Leader审核可採購/不能建BOM(PNRF)、不可採購/不能建BOM (CEO零件停產執行單)，拒绝
    #     如果是退件，則回到SCM user重新申請
    #     :return:
    #     """
    #     for class_part_category_id in self:
    #         if class_part_category_id.state == 'to scm leader approve':
    #             class_part_category_id.state = 'd class'
    #
    #         return self.env['warning_box'].info(title=u"提示信息", message=u"审核完成！")

class IacVendorDClassPartCategoryQmController(models.Model):
    _name = 'iac.dclass.part_category.qm_controller'
    _inherit = 'iac.class.part_category'
    _table = 'iac_class_part_category'

    # @api.multi
    # def action_batch_d_class_qm_controller_approve(self):
    #     """
    #     QM Controller审核特采放行，通过
    #     :return:
    #     """
    #     for class_part_category_id in self:
    #         if class_part_category_id.state == 'to qm controller approve':
    #             class_part_category_id.state = 'to qm leader approve'
    #
    #         return self.env['warning_box'].info(title=u"提示信息", message=u"审核完成！")
    #
    # @api.multi
    # def action_batch_d_class_qm_controller_disapprove(self):
    #     """
    #     QM Controller审核特采放行，拒绝
    #     如果是退件，則回到SCM user重新申請
    #     :return:
    #     """
    #     for class_part_category_id in self:
    #         if class_part_category_id.state == 'to qm controller approve':
    #             class_part_category_id.state = 'd class'
    #
    #         return self.env['warning_box'].info(title=u"提示信息", message=u"审核完成！")

class IacVendorDClassPartCategoryQmLeader(models.Model):
    _name = 'iac.dclass.part_category.qm_leader'
    _inherit = 'iac.class.part_category'
    _table = 'iac_class_part_category'