from django.db import migrations


def defaults(apps, schema_editor):
    alias = schema_editor.connection.alias
    Permission = apps.get_model("core", "AgentPermission")
    Role = apps.get_model("core", "AgentRole")
    role = Role.objects.using(alias).get(pk="customer_service")
    for code, label, scope in [
        ("catalog.read", "查詢服務與人員", "business"),
        ("availability.read", "查詢據點空檔", "business"),
        ("booking.read", "查詢自己的預約", "customer"),
        ("booking.create", "建立自己的預約", "customer"),
        ("booking.reschedule", "修改自己的預約", "customer"),
        ("booking.cancel", "取消自己的預約", "customer"),
    ]:
        permission, _ = Permission.objects.using(alias).get_or_create(
            code=code, defaults={"label": label, "scope": scope}
        )
        role.permissions.add(permission)
    apps.get_model("booking", "BookingSettings").objects.using(alias).get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("booking", "0001_initial"), ("core", "0002_defaults")]
    operations = [migrations.RunPython(defaults, migrations.RunPython.noop)]
