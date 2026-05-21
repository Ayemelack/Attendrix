import bcrypt

hashes = {
    'student1@attendrix.demo (Daniel Rockzy)': b'$2b$12$Jek/Gfca3HX3Xch37TMmk.5yFyA1orcc38Mrp5OgkTUTCXHlaAM4a',
    'lecturer1@attendrix.demo (Precious Acha)': b'$2b$12$eukZS1MlQNTTr2ewWNQtBOH2FWtJYC7GjdS5U8DXgx9Fhqu8xXkea',
}

candidates = ['password', '12345678', 'Pass1234', 'welcome', 'lecturer', 'student', 'Attendrix', 'attendrix', 'test123', 'precious', 'daniel', 'rockzy', 'acha', 'Daniel123', 'Precious123']

for pw in candidates:
    for user, h in hashes.items():
        if bcrypt.checkpw(pw.encode(), h):
            print(f'{user} -> password = "{pw}"')
print('Done checking')
