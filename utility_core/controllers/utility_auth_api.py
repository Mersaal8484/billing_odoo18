"""Utility Auth API controller for explicit field-role and scope checks."""

from odoo import _, http
from odoo.http import request


class UtilityAuthApi(http.Controller):

    @http.route(
        '/api/v1/utility/auth/roles',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def get_user_roles(self, **kwargs):
        """Return explicit field roles and the caller's assigned scope.

        A user without a recognized field role is rejected.  The endpoint must
        never make an unassigned user a meter reader by default, because the
        mobile client uses this response to choose its operating workflow.
        """
        user = request.env.user
        roles = user._get_mobile_role_flags()
        response = {
            'success': True,
            'user': {
                'id': user.id,
                'name': user.name,
                'login': user.login,
            },
            'roles': roles,
            'assigned_route_ids': user.assigned_route_ids.ids,
            'assigned_region_ids': user.assigned_region_ids.ids,
        }
        if not any(roles.values()):
            response.update({
                'success': False,
                'code': 'ROLE_NOT_ASSIGNED',
                'error': _('لا يملك هذا المستخدم دورًا ميدانيًا معتمدًا.'),
            })
        return response
