# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

import logging
_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    """Product Template Extension - Add video support"""
    _inherit = 'product.template'

    # Video support
    qr_video = fields.Binary(
        string=_('Product Video'),
        attachment=True,
        help=_('Upload product video (recommended under 30MB)')
    )
    qr_video_filename = fields.Char(
        string=_('Video Filename')
    )
    qr_video_url = fields.Char(
        string=_('Video URL'),
        help=_('External video URL (e.g. YouTube, CDN)')
    )

    # QR Ordering specific fields
    qr_short_desc = fields.Text(
        string=_('Short Description'),
        translate=True,
        help=_('Short description shown on QR ordering page')
    )
    qr_available = fields.Boolean(
        string=_('Available for QR Ordering'),
        default=True,
        help=_('Show on QR ordering page')
    )
    qr_highlight = fields.Boolean(
        string=_('Highlight'),
        default=False,
        help=_('Highlight this product on QR ordering page')
    )
    qr_pinned = fields.Boolean(
        string=_('Pinned'),
        default=False,
        help=_('Show in pinned video area (video carousel)')
    )
    qr_pinned_sequence = fields.Integer(
        string=_('Pinned Sequence'),
        default=10,
        help=_('Sort order in pinned area, lower number comes first')
    )
    qr_sold_out = fields.Boolean(
        string=_('Sold Out'),
        default=False,
        help=_('Temporary sold out status')
    )

    # Multi-language tags
    qr_tags = fields.Many2many(
        'qr.product.tag',
        string=_('Tags'),
        help=_('Product tags: spicy, vegetarian, recommended, etc.')
    )

    def get_qr_video_url(self):
        """Get video URL"""
        self.ensure_one()
        if self.qr_video_url:
            return self.qr_video_url
        elif self.qr_video:
            # Return Odoo attachment URL
            attachment = self.env['ir.attachment'].search([
                ('res_model', '=', 'product.template'),
                ('res_id', '=', self.id),
                ('res_field', '=', 'qr_video'),
            ], limit=1)
            if attachment:
                return f'/web/content/{attachment.id}'
        return None


class ProductProduct(models.Model):
    """Product Variant Extension"""
    _inherit = 'product.product'

    def get_qr_ordering_data(self, lang='zh_CN', pos_config=None):
        """Get QR ordering data

        Args:
            lang: Language code
            pos_config: POS config, used for tax and fiscal position
        """
        self.ensure_one()

        # Switch language context
        product = self.with_context(lang=lang)
        template = product.product_tmpl_id

        # Base price (excluding tax)
        price = self.lst_price

        # If POS config provided, calculate price with tax
        price_with_tax = price
        tax_rate = 0.0
        if pos_config:
            company = pos_config.company_id
            fiscal_position = pos_config.default_fiscal_position_id
            taxes = self.taxes_id.filtered(lambda t: t.company_id == company)
            if fiscal_position:
                taxes = fiscal_position.map_tax(taxes)
            if taxes:
                # Calculate price with tax
                tax_result = taxes.compute_all(price, product=self)
                price_with_tax = tax_result['total_included']
                if price > 0:
                    tax_rate = (price_with_tax - price) / price * 100

        return {
            'id': self.id,
            'name': product.name,
            'price': price,  # Price excluding tax
            'price_with_tax': price_with_tax,  # Price including tax
            'tax_rate': tax_rate,  # Tax rate percentage
            'description': template.qr_short_desc or template.description_sale or '',
            # Use public image URL (no auth required)
            'image_url': f'/qr/image/product/{self.id}?size=256',
            'video_url': template.get_qr_video_url(),
            'category_id': self.pos_categ_ids[0].id if self.pos_categ_ids else False,
            'category_name': self.pos_categ_ids[0].name if self.pos_categ_ids else '',
            'available': template.qr_available and not template.qr_sold_out,
            'sold_out': template.qr_sold_out,
            'highlight': template.qr_highlight,
            'pinned': template.qr_pinned,
            'pinned_sequence': template.qr_pinned_sequence,
            'tags': [{'id': t.id, 'name': t.name, 'color': t.color} for t in template.qr_tags],
        }


class QrProductTag(models.Model):
    """Product Tag"""
    _name = 'qr.product.tag'
    _description = _('Product Tag')
    _order = 'sequence, name'

    name = fields.Char(
        string=_('Tag Name'),
        required=True,
        translate=True
    )
    sequence = fields.Integer(
        string=_('Sequence'),
        default=10
    )
    color = fields.Char(
        string=_('Color'),
        default='#FF6B6B',
        help=_('Tag display color (hexadecimal)')
    )
    icon = fields.Char(
        string=_('Icon'),
        help=_('Icon name or emoji')
    )

    # Preset tags
    tag_type = fields.Selection([
        ('spicy', _('Spicy')),
        ('vegetarian', _('Vegetarian')),
        ('recommended', _('Recommended')),
        ('new', _('New')),
        ('popular', _('Popular')),
        ('healthy', _('Healthy')),
        ('custom', _('Custom')),
    ], string=_('Tag Type'), default='custom')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Tag name must be unique!'),
    ]
