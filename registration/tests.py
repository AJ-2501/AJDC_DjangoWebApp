from django.test import TestCase, Client
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from .models import Student


class AdminAccessAndPermissionsTest(TestCase):
    def setUp(self):
        self.client = Client()

        # Superuser
        self.superuser = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='Password123!'
        )

        # Staff user with no permissions
        self.staff_no_perm = User.objects.create_user(
            username='staff_noperm',
            email='noperm@test.com',
            password='Password123!',
            is_staff=True
        )

        # Staff user with View, Add, and Change permissions (No Delete)
        self.staff_user = User.objects.create_user(
            username='staff_records',
            email='staff@test.com',
            password='Password123!',
            is_staff=True
        )

        # Configure Group with permissions
        ct = ContentType.objects.get_for_model(Student)
        self.view_perm = Permission.objects.get(content_type=ct, codename='view_student')
        self.add_perm = Permission.objects.get(content_type=ct, codename='add_student')
        self.change_perm = Permission.objects.get(content_type=ct, codename='change_student')

        self.group = Group.objects.create(name='Student Records Staff Test')
        self.group.permissions.set([self.view_perm, self.add_perm, self.change_perm])
        self.staff_user.groups.add(self.group)

        # Existing student record for testing
        self.student = Student.objects.create(
            student_name='Alice Smith',
            program='BSIT',
            year_level=2,
            email='alice@example.com'
        )

    def test_superuser_has_full_admin_access(self):
        self.client.force_login(self.superuser)
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Students', content)
        self.assertIn('Users', content)

    def test_staff_without_student_permissions(self):
        self.client.force_login(self.staff_no_perm)
        response = self.client.get('/admin/registration/student/')
        self.assertEqual(response.status_code, 403)

    def test_staff_view_student_list(self):
        self.client.force_login(self.staff_user)
        response = self.client.get('/admin/registration/student/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alice Smith')

    def test_staff_add_student(self):
        self.client.force_login(self.staff_user)
        response = self.client.post('/admin/registration/student/add/', {
            'student_name': 'Bob Jones',
            'program': 'BSCS',
            'year_level': 1,
            'email': 'bob@example.com',
            '_save': 'Save'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Student.objects.filter(student_name='Bob Jones').exists())

    def test_staff_change_student(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(f'/admin/registration/student/{self.student.pk}/change/', {
            'student_name': 'Alice Smith Updated',
            'program': 'BSIT',
            'year_level': 3,
            'email': 'alice@example.com',
            '_save': 'Save'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.student_name, 'Alice Smith Updated')
        self.assertEqual(self.student.year_level, 3)

    def test_staff_cannot_delete_student(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(f'/admin/registration/student/{self.student.pk}/delete/')
        self.assertEqual(response.status_code, 403)
        post_response = self.client.post(f'/admin/registration/student/{self.student.pk}/delete/', {'post': 'yes'})
        self.assertEqual(post_response.status_code, 403)
        self.assertTrue(Student.objects.filter(pk=self.student.pk).exists())

    def test_staff_cannot_manage_users(self):
        self.client.force_login(self.staff_user)
        response = self.client.get('/admin/auth/user/')
        self.assertEqual(response.status_code, 403)

    def test_invalid_student_data_rejected(self):
        self.client.force_login(self.staff_user)
        response = self.client.post('/admin/registration/student/add/', {
            'student_name': 'Charlie Brown',
            'program': 'BSIT',
            'year_level': 1,
            'email': 'invalid-email-address',
            '_save': 'Save'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter a valid email address.')
        self.assertFalse(Student.objects.filter(student_name='Charlie Brown').exists())

    def test_logout_ends_authenticated_session(self):
        self.client.force_login(self.staff_user)
        self.client.logout()
        response = self.client.get('/admin/registration/student/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.headers['Location'])
