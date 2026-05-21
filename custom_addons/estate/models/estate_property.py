from odoo import fields, models;
from datetime import datetime,timedelta;  


class EstateProperty(models.Model):
    _name = "estate_property"
    _description = "Real Estate Property Model"


    name=fields.Char(required=True)
    description=fields.Text()
    postcode=fields.Char()
    date_availability=fields.Date(copy=False,default= lambda self:datetime.today() +timedelta(days=90))
    expected_price=fields.Float(required=True)
    selling_price=fields.Float(default=1200, readonly=True)
    bedrooms=fields.Integer(default=2)
    living_area=fields.Integer()
    facades=fields.Integer()
    garage=fields.Boolean()
    garden= fields.Boolean()
    garden_area=fields.Integer()
    garden_oreintation=fields.Selection( selection=[('North','North'),('South','South'),('East','East'),('West','West')])
    active=fields.Boolean(default=True)
    state=fields.Selection(selection=[('New','New'),('Offer Recieved','Offer Received'),('Offer Accepted','Offer Accepted'),('Sold','Sold'),('Cancelled','Cancelled')])


    
    