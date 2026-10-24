# frontend/ (owner: Mit)

Not scaffolded yet: task **M0** in `tasks/mit.md` creates the Next.js app here:

```bash
npx create-next-app@latest . --ts --tailwind --eslint --app --src-dir --use-npm
npm i -D openapi-typescript
# add "gen:api": "openapi-typescript http://localhost:8000/openapi.json -o src/lib/api.d.ts"
```

The CI frontend job starts running automatically once `package.json` exists.
