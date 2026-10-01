import hashlib
import io
import logging
from PIL import Image, UnidentifiedImageError

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from ..adapters.media.attachment import AttachmentMediaAdapter
from ..adapters.media.filesystem import FilesystemMediaAdapter

_logger = logging.getLogger(__name__)


class UtilityMediaService(models.AbstractModel):
    _name = 'utility.media.service'
    _description = 'مخدم إدارة الوسائط والصور الرقمية (Central Media Service)'

    @api.model
    def get_media_adapter(self):
        """إرجاع المحول الخاص بتخزين الوسائط والصور الرقمية دون silent fallback"""
        backend = self.env['ir.config_parameter'].sudo().get_param('utility.media_backend', 'attachment')
        adapters = {
            'attachment': AttachmentMediaAdapter,
            'filesystem': FilesystemMediaAdapter,
        }
        adapter_class = adapters.get(backend)
        if not adapter_class:
            raise UserError(_("نوع محول تخزين الوسائط غير معروف: %s") % backend)
        return adapter_class(self.env)

    @api.model
    def calculate_sha256(self, raw_bytes):
        return hashlib.sha256(raw_bytes).hexdigest() if raw_bytes else ''

    @api.model
    def generate_image_variants(self, raw_bytes):
        """إرجاع بيانات الصورة للأصل دون توليد مصغرات إضافية (Standard Single Attachment)"""
        if not raw_bytes:
            return {'original': b'', 'review': b'', 'thumbnail': b''}
        return {
            'original': raw_bytes,
            'review': raw_bytes,
            'thumbnail': raw_bytes,
        }

    @api.model
    def _detect_mime_from_bytes(self, raw_bytes):
        """اكتشاف نوع MIME الحقيقي من بصمة البايتات الأولية للصورة"""
        format_to_mime = {
            'JPEG': 'image/jpeg',
            'PNG': 'image/png',
            'WEBP': 'image/webp',
            'GIF': 'image/gif',
            'BMP': 'image/bmp',
            'TIFF': 'image/tiff',
        }
        try:
            image = Image.open(io.BytesIO(raw_bytes))
            fmt = image.format
            image.close()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValidationError(_("تعذر اكتشاف نوع الصورة الحقيقي.")) from exc
        try:
            return format_to_mime[fmt]
        except KeyError as exc:
            raise ValidationError(_("صيغة الصورة غير مدعومة: %s") % fmt) from exc

    @api.model
    def store_media(self, file_data, filename, mimetype='image/jpeg', reading_id=False, batch_id=False, asset_type='meter_reading'):
        """تخزين وسائط جديدة ومعالجتها عبر Adapter وتوليد النسخ.

        العقد: file_data يجب أن يكون raw bytes (صورة ثنائية حقيقية).
        أي ناقل (UI / REST / AMI) مسؤول عن فك Base64 قبل الاستدعاء.
        """
        if not file_data:
            raise ValidationError(_("بيانات الصورة أو الملف فارغة."))

        if isinstance(file_data, str):
            raise ValidationError(_(
                "Media service لا يقبل Base64 strings. "
                "يجب فك الترميز إلى raw bytes قبل الاستدعاء."
            ))

        raw_bytes = bytes(file_data)

        try:
            img = Image.open(io.BytesIO(raw_bytes))
            img.verify()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValidationError(_(
                "بيانات الصورة غير صالحة — لا يمكن فتحها كصورة: %s"
            ) % filename) from exc

        mimetype = self._detect_mime_from_bytes(raw_bytes)

        sha256_hash = self.calculate_sha256(raw_bytes)
        file_size = len(raw_bytes)
        active_backend = self.env['ir.config_parameter'].sudo().get_param('utility.media_backend', 'attachment')

        # فحص وجود أصل سابق بنفس البصمة لإعادة استخدام الـ Attachment الثنائي دون تكرار تخزين الملف
        existing_asset = self.env['utility.media.asset'].sudo().search([
            ('sha256', '=', sha256_hash),
            ('file_size', '=', file_size),
            ('state', '=', 'ready'),
        ], limit=1)

        create_vals = {
            'original_filename': filename,
            'mime_type': mimetype,
            'file_size': file_size,
            'sha256': sha256_hash,
            'asset_type': asset_type,
            'reading_id': reading_id,
            'state': 'processing',
            'storage_backend': active_backend,
        }
        if batch_id and 'batch_id' in self.env['utility.media.asset']._fields:
            create_vals['batch_id'] = batch_id

        if existing_asset and existing_asset.original_attachment_id:
            _logger.info("Reusing binary attachments from SHA256 match asset %s for new evidence record", existing_asset.asset_uuid)
            reused_vals = dict(create_vals, **{
                'state': 'ready',
                'storage_backend': existing_asset.storage_backend or active_backend,
                'original_attachment_id': existing_asset.original_attachment_id.id,
                'review_attachment_id': existing_asset.original_attachment_id.id,
                'thumbnail_attachment_id': existing_asset.original_attachment_id.id,
                'processed_at': fields.Datetime.now(),
            })
            new_asset = self.env['utility.media.asset'].sudo().create(reused_vals)
            if reading_id:
                reading = self.env['utility.reading'].browse(reading_id)
                if reading.exists() and not reading.attachment_id:
                    reading.sudo().with_context(_bypass_reading_protection=True).write({
                        'attachment_id': existing_asset.original_attachment_id.id,
                    })
            return new_asset

        # إنشاء سجل الأصل الرقمي
        asset = self.env['utility.media.asset'].sudo().create(create_vals)

        try:
            adapter = self.get_media_adapter()

            # تخزين المرفق القياسي الأصلي الوحيد (Standard Attachment بدون توليد أو تخزين أي صور مصغرة)
            target_res_model = 'utility.reading' if reading_id else 'utility.media.asset'
            target_res_id = reading_id or asset.id
            orig_att = adapter.store(
                file_data=raw_bytes,
                filename=filename,
                mimetype=mimetype,
                metadata={'res_model': target_res_model, 'res_id': target_res_id, 'asset_uuid': asset.asset_uuid}
            )

            asset.write({
                'original_attachment_id': orig_att.id,
                'review_attachment_id': orig_att.id,
                'thumbnail_attachment_id': orig_att.id,
                'state': 'ready',
                'processed_at': fields.Datetime.now(),
            })

            if reading_id:
                reading = self.env['utility.reading'].browse(reading_id)
                if reading.exists() and not reading.attachment_id:
                    reading.sudo().with_context(_bypass_reading_protection=True).write({
                        'attachment_id': orig_att.id,
                    })

            return asset
        except (AccessError, UserError, ValidationError, OSError) as exc:
            asset.write({
                'state': 'failed',
                'error_code': 'STORAGE_ERROR',
                'error_message': str(exc),
            })
            _logger.error("Failed to store media asset %s: %s", asset.asset_uuid, str(exc))
            raise

    @api.model
    def retrieve_media(self, asset, variant='original'):
        if not asset or not asset.exists():
            return b''
        adapter = self.get_media_adapter()
        return adapter.retrieve(asset, variant=variant)

    @api.model
    def get_media_url(self, asset, variant='original'):
        if not asset or not asset.exists():
            return ''
        return asset.get_variant_url(variant=variant)
