print(env['ir.rule'].search([('model_id.model', '=', 'utility.meter')]).mapped('domain_force'))  
