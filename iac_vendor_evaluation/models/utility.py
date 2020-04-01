# -*- coding: utf-8 -*-

def send_to_email(self, object_id=None, template_name=None):
    """发送邮件"""
    try:
        template = self.env.ref(template_name)
        template.send_mail(object_id, force_send=True)
    except:
        pass

