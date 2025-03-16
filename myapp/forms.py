from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, PasswordField, FileField, SubmitField, HiddenField, SelectField
from wtforms.validators import DataRequired,Email,Length

class YourFormClass(FlaskForm):
    some_field = StringField('Some Field')
    submit = SubmitField('Submit')

class DispatchTruckForm(FlaskForm):
    location = HiddenField('Location', validators=[DataRequired()])
    submit = SubmitField('Dispatch Trucks')

class LitterHotspotForm(FlaskForm):
    location = StringField('Location', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    image = FileField('Upload Image')
    submit = SubmitField('Report Hotspot')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=25)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])   

class UserManagementForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    role = SelectField('Role', choices=[('admin', 'Admin'), ('normal', 'Normal User')], validators=[DataRequired()])
    submit = SubmitField('Update User')

class BinStatusUpdateForm(FlaskForm):
    bin_id = StringField('Bin ID', validators=[DataRequired()])
    status = SelectField('Status', choices=[('full', 'Full'), ('empty', 'Empty')], validators=[DataRequired()])
    submit = SubmitField('Update Status')


