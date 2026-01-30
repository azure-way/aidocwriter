import { JobDashboard } from "../../newdocument/page";

type JobPageProps = {
  params: Promise<{
    jobId: string;
  }>;
};

export default async function JobPage({ params }: JobPageProps) {
  const resolved = await params;
  const jobId = decodeURIComponent(resolved.jobId);
  return <JobDashboard initialJobId={jobId} />;
}
