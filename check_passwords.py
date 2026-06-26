import bcrypt

hashes = {
    'admin@attendrix.demo': b'$2b$12$j7HCA8ejM.lq1.Q7OmE8Q.8m.m.Dfbn6bwK3VJolQu9MAmi/e48Om',
    'student1@attendrix.demo': b'$2b$12$Jek/Gfca3HX3Xch37TMmk.5yFyA1orcc38Mrp5OgkTUTCXHlaAM4a',
    'lecturer1@attendrix.demo': b'$2b$12$eukZS1MlQNTTr2ewWNQtBOH2FWtJYC7GjdS5U8DXgx9Fhqu8xXkea',
}

candidates = ['password123', 'admin123', 'pass123', 'password', 'demo123', 'Attendrix123', 'Admin123', 'Password123', '12345678']

for pw in candidates:
    for user, h in hashes.items():
        if bcrypt.checkpw(pw.encode(), h):
            print(f'{user} -> password = "{pw}"')
